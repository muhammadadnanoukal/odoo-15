# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from werkzeug import urls
from lxml import etree, objectify
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.altanmia_payment_hyperpay.const import PAYMENT_STATUS_MAPPING
from odoo.addons.altanmia_payment_hyperpay.controllers.main import HyperPayController

import json

_logger = logging.getLogger(__name__)


def _is_cancel(code):
    for exp in PAYMENT_STATUS_MAPPING['done']:
        if bool(re.search(exp, code)):
            return True
    return False


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider, prefix=None, separator='-', **kwargs):
        """ Override of payment to ensure that Ogone requirements for references are satisfied.

        Ogone requirements for references are as follows:
        - References must be unique at provider level for a given merchant account.
          This is satisfied by singularizing the prefix with the current datetime. If two
          transactions are created simultaneously, `_compute_reference` ensures the uniqueness of
          references by suffixing a sequence number.

        :param str provider: The provider of the acquirer handling the transaction
        :param str prefix: The custom prefix used to compute the full reference
        :param str separator: The custom separator used to separate the prefix from the suffix
        :return: The unique reference for the transaction
        :rtype: str
        """
        if provider != 'hyperpay':
            return super()._compute_reference(provider, prefix=prefix, **kwargs)

        if not prefix:
            # If no prefix is provided, it could mean that a module has passed a kwarg intended for
            # the `_compute_reference_prefix` method, as it is only called if the prefix is empty.
            # We call it manually here because singularizing the prefix would generate a default
            # value if it was empty, hence preventing the method from ever being called and the
            # transaction from received a reference named after the related document.
            prefix = self.sudo()._compute_reference_prefix(provider, separator, **kwargs) or None

        prefix = payment_utils.singularize_reference_prefix(prefix=prefix, max_length=40)
        return super()._compute_reference(provider, prefix=prefix, **kwargs)

    def _get_specific_rendering_values(self, processing_values):
        """ Override of payment to return Ogone-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.acquirer_id.provider != 'hyperpay':
            return res
        partner_first_name, partner_last_name = payment_utils.split_partner_name(self.partner_name)

        init_checkout = {
            'entityId': self.acquirer_id.hyperpay_entity_id,
            'amount': ("%.2f"%self.amount),
            'merchantTransactionId': self.reference,
            'customer.email': self.partner_email,
            'billing.street1': self.partner_address,
            'billing.city': self.partner_city,
            'billing.state': self.partner_state_id.name,
            'billing.country': self.partner_country_id.code,
            'billing.postcode': self.partner_zip,
            'customer.givenName': partner_first_name,
            'customer.surname': partner_last_name,
            'currency': self.currency_id.name,
            'paymentType': 'DB'
        }

        if self.tokenize:
            init_checkout.update({
                'createRegistration': True,
                'standingInstruction.source': 'CIT',
                'standingInstruction.mode': 'INITIAL',
            })

        response = self.acquirer_id._make_request(init_checkout, endpoint= '/checkouts')

        try:
            response_content = json.loads(response)
        except Exception as e:
            raise ValidationError("HyperPay: " + "Received badly structured response from the API.")

        return_url = urls.url_join(self.acquirer_id.get_base_url(), HyperPayController._return_url)
        js_url = self.acquirer_id._hyperpay_get_api_url()+"/paymentWidgets.js?checkoutId="+response_content['id']
        form_url =  urls.url_join(self.acquirer_id.get_base_url(), HyperPayController._redirect_form)
        rendering_values = {
            'js_url': js_url,
            'form_url':form_url,
            'back_url': return_url
        }

        return rendering_values

    def _get_specific_processing_values(self, processing_values):
        """ Override of payment to return an access token as acquirer-specific processing values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values of the transaction
        :return: The dict of acquirer-specific processing values
        :rtype: dict
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider != 'hyperpay':
            return res

        return {
            'access_token': payment_utils.generate_access_token(
                processing_values['reference'], processing_values['partner_id']
            )
        }

    def _send_payment_request(self):
        """ Override of payment to send a payment request to HyperPay.

        Note: self.ensure_one()

        :return: None
        :raise: UserError if the transaction is not linked to a token
        """

        super()._send_payment_request()
        if self.provider != 'hyperpay':
            return

        if not self.token_id:
            raise UserError("HyperPay: " + _("The transaction is not linked to a token."))
        return_url = urls.url_join(self.acquirer_id.get_base_url(), HyperPayController._return_url)
        data = {
            # DirectLink parameters
            'entityId': self.acquirer_id.hyperpay_entity_id,
            'amount': ("%.2f"%self.amount),
            'currency': self.currency_id.name,
            'paymentType': 'DB',
            'standingInstruction.source': 'CIT',
            'standingInstruction.mode': 'REPEATED',
            'shopperResultUrl': return_url,
            'merchantTransactionId': self.reference,
            'standingInstruction.type': 'UNSCHEDULED',
        }

        _logger.info(
            "making payment request:\n%s",
            pprint.pformat({k: v for k, v in data.items() if k != 'PSWD'})
        )  # Log the payment request data without the password
        response = self.acquirer_id._make_request(payload=data, token=self.token_id)

        try:
            response_content = json.loads(response)
        except Exception as e:
            raise ValidationError("HyperPay: " + "Received badly structured response from the API.")

        #feedback_data = {'reference': response_content.get('merchantTransactionId'), 'response': response_content}

        _logger.info("entering _handle_feedback_data with data:\n%s", pprint.pformat(response_content))
        self._handle_feedback_data('ogone', response_content)

    @api.model
    def _get_tx_from_feedback_data(self, provider, data):
        """ Override of payment to find the transaction based on HyperPay data.

        :param str provider: The provider of the acquirer that handled the transaction
        :param dict data: The feedback data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_feedback_data(provider, data)
        if provider != 'hyperpay':
            return tx

        reference = data.get('merchantTransactionId')
        tx = self.search([('reference', '=', reference), ('provider', '=', 'hyperpay')])
        if not tx:
            raise ValidationError(
                "hyperPay: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_feedback_data(self, data):
        """ Override of payment to process the transaction based on Paypal data.

        Note: self.ensure_one()

        :param dict data: The feedback data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_feedback_data(data)
        if self.provider != 'hyperpay':
            return
        payment_status = data.get('result')

        if self._is_pending(payment_status['code']):
            self._set_pending(state_message=payment_status['description'])

        elif self._is_done(payment_status['code']):
            trans_token_exist = 'registrationId' in data
            if self.tokenize and trans_token_exist:
                self._get_tokenize_from_feedback_data(data)
            self._set_done(state_message=payment_status['description'])

        elif self._is_cancel(payment_status['code']):
            self._set_canceled(state_message=payment_status['description'])
        else:
            _logger.info("received data with invalid payment status: %s", payment_status)
            self._set_error(
                "HyperPay: " + _("Received data with invalid payment status:%s - %s" %(payment_status['code'],payment_status['description']))
            )

    def _get_tokenize_from_feedback_data(self, data):
        """ Create a token from feedback data.

        :param dict data: The feedback data sent by the provider
        :return: None
        """
        token_name = payment_utils.build_token_name()
        token = self.env['payment.token'].create({
            'acquirer_id': self.acquirer_id.id,
            'name': token_name,  # Already padded with 'X's
            'partner_id': self.partner_id.id,
            'acquirer_ref': data['registrationId'],
            'verified': True,  # The payment is authorized, so the payment method is valid
        })
        self.write({
            'token_id': token.id,
            'tokenize': False,
        })
        _logger.info(
            "created token with id %s for partner with id %s", token.id, self.partner_id.id
        )

    def _is_pending(self, code):
        for exp in PAYMENT_STATUS_MAPPING['pending']:
            if bool(re.search(exp, code)):
                return True
        return False

    def _is_done(self, code):
        for exp in PAYMENT_STATUS_MAPPING['done']:
            if bool(re.search(exp, code)):
                return True
        return False

    def _is_cancel(self, code):
        for exp in PAYMENT_STATUS_MAPPING['cancel']:
            if bool(re.search(exp, code)):
                return True
        return False

