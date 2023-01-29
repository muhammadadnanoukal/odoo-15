# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from odoo import _, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.payment import utils as payment_utils

import json
_logger = logging.getLogger(__name__)




class HyperPayController(http.Controller):
    _return_url = '/payment/hyperpay/return'

    _redirect_form = '/payment/hyperpay/form'

    @http.route(_return_url, type='http', auth='public',methods=['GET', 'POST'], csrf=False)
    def hyperpay_return_process(self, id, resourcePath):
        # Handle the feedback data
        acquirer = request.env['payment.acquirer'].sudo().search([
            ('provider', '=', 'hyperpay'),
        ])
        resourcePath = resourcePath.replace('/v1','')
        endpoint = resourcePath+'?entityId='+acquirer.hyperpay_entity_id
        response = acquirer._make_request(payload={},method='GET', endpoint=endpoint)


        try:
            response_content = json.loads(response)
        except Exception as e:
            raise ValidationError("HyperPay: " + "Received badly structured response from the API.")

        _logger.info("entering _handle_feedback_data with data:\n%s", pprint.pformat(response_content))

        request.env['payment.transaction'].sudo()._handle_feedback_data('hyperpay', response_content)
        #request.env['payment.transaction'].sudo()._handle_feedback_data('ogone', data)
        return request.redirect('/payment/status')

    @http.route(_redirect_form, type='http', auth='public',methods=['GET', 'POST'], csrf=False)
    def hyperpay_payment_form(self, back_url, js_url):

        return request.render("altanmia_payment_hyperpay.hyperpay_form", {
            'back_url': back_url,
            'js_url': js_url,
        })
