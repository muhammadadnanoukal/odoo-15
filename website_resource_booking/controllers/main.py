# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import http
from odoo.http import request
from odoo.osv import expression

from odoo.addons.altanmia_resource_booking.controllers.main import Booking
from odoo.addons.website.controllers.main import QueryURL


class WebsiteBooking(Booking):

    #----------------------------------------------------------
    # Appointment HTTP Routes
    #----------------------------------------------------------

    @http.route()
    def booking_profiles_list(self, page=1, **kwargs):
        """
        Display the appointments to choose (the display depends of a custom option called 'Card Design')

        :param page: the page number displayed when the appointments are organized by cards

        A param filter_appointment_type_ids can be passed to display a define selection of appointments types.
        This param is propagated through templates to allow people to go back with the initial appointment
        types filter selection
        """
        cards_layout = request.website.viewref('website_resource_booking.booking_profiles_list_cards').active

        if cards_layout:
            return request.render('website_resource_booking.booking_profile_cards_layout',
                                  self._prepare_booking_cards_data(page, **kwargs))
        else:
            return super().booking_profiles_list(page, **kwargs)

    #----------------------------------------------------------
    # Utility Methods
    #----------------------------------------------------------

    def _prepare_booking_cards_data(self, page, **kwargs):
        """
            Compute specific data for the cards layout like the the search bar and the pager.
        """
        domain = self._booking_base_domain(kwargs.get('filter_appointment_type_ids'))

        booking = request.env['tanmia.booking.book.profile']
        website = request.website

        # Add domain related to the search bar
        if kwargs.get('search'):
            domain = expression.AND([domain, [('name', 'ilike', kwargs.get('search'))]])

        APPOINTMENTS_PER_PAGE = 12
        appointment_count = booking.search_count(domain)
        pager = website.pager(
            url='/booking',
            url_args=kwargs,
            total=appointment_count,
            page=page,
            step=APPOINTMENTS_PER_PAGE,
            scope=5,
        )

        booking_profiles = booking.search(domain, limit=APPOINTMENTS_PER_PAGE, offset=pager['offset'])
        keep = QueryURL('/booking', search=kwargs.get('search'), filter_appointment_type_ids=kwargs.get('filter_appointment_type_ids'))

        return {
            'booking_profiles': booking_profiles,
            'current_search': kwargs.get('search'),
            'keep': keep,
            'pager': pager,
        }

    def _get_customer_partner(self):
        partner = super()._get_customer_partner()
        if not partner:
            partner = request.env['website.visitor']._get_visitor_from_request().partner_id
        return partner

    def _get_customer_country(self):
        """
            Find the country from the geoip lib or fallback on the user or the visitor
        """
        country = super()._get_customer_country()
        if not country:
            visitor = request.env['website.visitor']._get_visitor_from_request()
            country = visitor.country_id
        return country
