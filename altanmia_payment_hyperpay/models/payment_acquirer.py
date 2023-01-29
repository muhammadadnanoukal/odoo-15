# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from werkzeug import urls
from odoo.addons.altanmia_payment_hyperpay.controllers.main import HyperPayController

from odoo.addons.altanmia_payment_hyperpay.const import SUPPORTED_CURRENCIES, SUPPORTED_BRANDS

import requests
from odoo.exceptions import ValidationError, UserError
import json
_logger = logging.getLogger(__name__)


class PaymentAcquirer(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
        selection_add=[('hyperpay', "HyperPay")], ondelete={'hyperpay': 'set default'})
    hyperpay_entity_id = fields.Char(
        string="Entity Id",
        help="""Entity ID:
        Unique ID provided by HyperPay,
        The entity required to authorize the request. This should be the channel entity identifier.
        In case channel dispatching is activated then it should be the merchant entity identifier.""",
        required_if_provider='hyperpay')

    hyperpay_token = fields.Char(string="Access Token", help="""access token:
     associated with entered entity ID. Authorization header with Bearer authentication scheme.
     Access token can be taken from the backend UI under Administration > Account data > Merchant / Channel Info 
     only if you have specific administration rights."""
                                ,required_if_provider='hyperpay' ,groups='base.group_system')


    @api.model
    def _get_compatible_acquirers(self, *args, currency_id=None, **kwargs):
        """ Override of payment to unlist PayPal acquirers when the currency is not supported. """
        acquirers = super()._get_compatible_acquirers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name not in SUPPORTED_CURRENCIES:
            acquirers = acquirers.filtered(lambda a: a.provider != 'hyperpay')

        return acquirers

    def get_compatible_brands(self):
        return SUPPORTED_BRANDS

    def _hyperpay_get_api_url(self):
        """ Return the API URL according to the acquirer state.
        Note: self.ensure_one()
        :return: The API URL
        :rtype: str
        """
        self.ensure_one()

        if self.state == 'enabled':
            return 'https://eu-prod.oppwa.com/v1'
        else:
            return 'https://eu-test.oppwa.com/v1'


    def _make_request(self, payload=None, method='POST', token=None, endpoint=None):

        """ Make a request to one of Hyperpay APIs.
        Note: self.ensure_one()
        :param dict payload: The payload of the request
        :param str method: The HTTP method of the request
        :return The content of the response
        :rtype: bytes
        :raise: ValidationError if an HTTP error occurs
        """
        self.ensure_one()

        if endpoint is None:
            endpoint = '/payments' if not token else f"/registrations/{token.acquirer_ref}/payments"

        url = self._hyperpay_get_api_url()+ endpoint
        _logger.info("url %s" % url)

        headers = {'AUTHORIZATION': f'Bearer {self.hyperpay_token}'}

        try:
            response = requests.request(method, url, headers=headers, data=payload, timeout=60)
            _logger.info("response %s" %response.content.decode("utf-8"))
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            _logger.exception("unable to reach endpoint at %s", url)
            raise ValidationError("HyperPay: " + _("Could not establish the connection to the API."))
        except requests.exceptions.HTTPError:
            _logger.exception("invalid API request at %s with data %s", url, payload)
            raise ValidationError("HyperPay: " + _("The communication with the API failed."))
        return response.content.decode("utf-8")

    def _get_default_payment_method_id(self):
        self.ensure_one()
        if self.provider != 'hyperpay':
            return super()._get_default_payment_method_id()
        return self.env.ref('altanmia_payment_hyperpay.payment_method_hyperpay').id