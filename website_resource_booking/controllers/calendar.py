# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.altanmia_resource_booking.controllers.calendar import BookingController
from odoo.osv.expression import AND

class WebsiteBookingController(BookingController):
    def _get_employee_booking_profile_domain(self, employee):
        domain = super()._get_employee_booking_profile_domain(employee)
        return AND([domain, [('website_published', '=', True)]])
