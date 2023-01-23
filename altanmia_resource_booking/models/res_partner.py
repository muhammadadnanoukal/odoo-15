# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, time
from odoo import api, fields, models, _, Command

import pytz

from odoo import models
from odoo.addons.website.models import ir_http

class Partner(models.Model):
    _inherit = "res.partner"
    last_website_booking_id = fields.Many2one('sale.order', compute='_compute_last_website_book_id', string='Last Online Sales Order')

    def calendar_verify_availability(self, date_start, date_end):
        """ Verify availability of the partner(s) between 2 datetimes on their calendar.

        :param datetime date_start: beginning of slot boundary. Not timezoned UTC;
        :param datetime date_end: end of slot boundary. Not timezoned UTC;
        """
        all_events = self.env['calendar.event']
        if self:
            all_events = self.env['calendar.event'].search(
                ['&',
                 ('partner_ids', 'in', self.ids),
                 '&',
                 ('stop', '>', datetime.combine(date_start, time.min)),
                 ('start', '<', datetime.combine(date_end, time.max)),
                ],
                order='start asc',
            )
        aware_offset = date_start.tzinfo is not None and date_start.tzinfo.utcoffset(date_start) is not None

        for event in all_events:

            estart = pytz.utc.localize(event.start) if aware_offset else event.start
            eend = pytz.utc.localize(event.stop) if aware_offset else event.stop
            print(estart,eend,date_start,date_end)

            if event.allday or ( estart < date_end and eend > date_start):

                if event.attendee_ids.search(
                        [('state', '!=', 'declined'),
                         ('partner_id', 'in', self.ids)]
                    ):
                    return False
        return True

    def _compute_last_website_book_id(self):
        book_order = self.env['sale.order']
        for partner in self:
            is_public = any(u._is_public() for u in partner.with_context(active_test=False).user_ids)
            website = ir_http.get_request_website()
            if website and not is_public:
                partner.last_website_booking_id = book_order.search([
                    ('partner_id', '=', partner.id),
                    ('website_id', '=', website.id),
                    ('booking_order', '=', True),
                    ('state', '=', 'draft'),
                ], order='write_date desc', limit=1)
            else:
                partner.last_website_booking_id = book_order  # Not in a website context or public User

    def _compute_last_website_so_id(self):
        SaleOrder = self.env['sale.order']
        for partner in self:
            is_public = any(u._is_public() for u in partner.with_context(active_test=False).user_ids)
            website = ir_http.get_request_website()
            if website and not is_public:
                partner.last_website_so_id = SaleOrder.search([
                    ('partner_id', '=', partner.id),
                    ('website_id', '=', website.id),
                    ('booking_order', '=', False),
                    ('state', '=', 'draft'),
                ], order='write_date desc', limit=1)
            else:
                partner.last_website_so_id = SaleOrder  # Not in a website context or public User

