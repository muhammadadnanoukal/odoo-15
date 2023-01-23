# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug import urls
from werkzeug.urls import url_encode, url_join

from odoo import fields, _
from odoo.addons.calendar.controllers.main import CalendarController
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.http_routing.models.ir_http import slug
from odoo.http import request, route


class BookingController(CalendarController):

    @route(website=True)
    def view_meeting(self, token, id):
        """Redirect the internal logged in user to the form view of calendar.event, and redirect
           regular attendees to the website page of the calendar.event for online appointments"""
        super(BookingController, self).view_meeting(token, id)
        attendee = request.env['calendar.attendee'].sudo().search([
            ('access_token', '=', token),
            ('event_id', '=', int(id))])
        if not attendee:
            return request.render("appointment.appointment_invalid", {})

        # If user is internal and logged, redirect to form view of event
        if request.env.user.has_group('base.group_user'):
            url_params = urls.url_encode({
                'id': id,
                'view_type': 'form',
                'model': attendee.event_id._name,
            })
            return request.redirect('/web?db=%s#%s' % (request.env.cr.dbname, url_params))

        request.session['timezone'] = attendee.partner_id.tz
        if not attendee.event_id.access_token:
            attendee.event_id._generate_access_token()
        return request.redirect('/booking/view/%s?partner_id=%s' % (attendee.event_id.access_token, attendee.partner_id.id))

    @route('/booking/booking_profile/create_custom', type='json', auth='user')
    def booking_crerate_custome_profile(self, slots):
        """
        Return the info (id and url) of the custom appointment type
        that is created with the time slots in the calendar.

        Users would typically use this feature to create a custom
        appointment type for a specific customer and suggest a few
        hand-picked slots from the calendar view that work best for that
        appointment.

        Contrary to regular appointment types that are meant to be re-used
        several times week after week (e.g.: "Schedule Demo"), this category
        of appointment type will be unlink after some time has passed.

        - slots format:
            [{
                'start': '2021-06-25 13:30:00',
                'end': '2021-06-25 15:30:00',
                'allday': False,
            }, {
                'start': '2021-06-25 22:00:00',
                'end': '2021-06-26 22:00:00',
                'allday': True,
            },...]
        The timezone used for the slots is UTC
        """
        if not slots:
            raise ValidationError(_("A list of slots information is needed to create a custom appointment type"))
        # Check if the user is a member of group_user to avoid portal user and the like to create appointment types
        if not request.env.user.user_has_groups('base.group_user'):
            raise AccessError(_("Access Denied"))
        booking_profile = request.env['tanmia.booking.book.profile'].sudo().create({
            'category': 'custom',
            'slot_ids': [(0, 0, {
                'start_datetime': fields.Datetime.from_string(slot.get('start')),
                'end_datetime': fields.Datetime.from_string(slot.get('end')),
                'allday': slot.get('allday'),
                'slot_type': 'unique',
            }) for slot in slots],
        })

        return self._get_employee_booking_info(booking_profile)

    @route('/booking/booking_profile/search_create_work_hours', type='json', auth='user')
    def booking_search_create_work_hours_booking_profile(self):
        """
        Return the info (id and url) of the work hours appointment type of the actual employee.

        Search and return the work_hours appointment type for the employee.
        In case it doesn't exist yet, it creates a work_hours appointment type that
        uses a slot of 1 hour every 30 minutes during it's working hour.
        We emcopass the whole week to avoid computation in case the working hours
        of the employee are modified at a later date.
        """
        booking_profile = request.env['tanmia.booking.book.profile'].search([
            ('category', '=', 'work_hours'),
            ('employee_ids', 'in', request.env.user.employee_id.ids)])
        if not booking_profile:
            # Check if the user is a member of group_user to avoid portal user and the like to create appointment types
            if not request.env.user.user_has_groups('base.group_user'):
                raise AccessError(_("Access Denied"))
            booking_profile = request.env['tanmia.booking.book.profile'].sudo().create({
                'max_schedule_days': 30,
                'category': 'work_hours',
                'slot_ids': [(0, 0, {
                    'weekday': str(day + 1),
                    'start_hour': hour * 0.5,
                    'end_hour': 23.99,
                }) for hour in range(2) for day in range(7)],
            })

        return self._get_employee_booking_info(booking_profile)

    @route('/booking/booking_profile/get_employee_booking_profile', type='json', auth='user')
    def booking_get_employee_booking_profile(self):
        employee_id = request.env.user.employee_id.id
        booking_profile_info = []
        if employee_id:
            domain = self._get_employee_booking_profile_domain(employee_id)
            booking_profile_info = request.env['tanmia.booking.book.profile'].search_read(domain, ['name', 'category'])
        return {
            'employee_id': employee_id,
            'booking_profile_info': booking_profile_info,
        }

    def _get_employee_booking_profile_domain(self, employee_id):
        return [('employee_ids', 'in', [employee_id]), ('category', '!=', 'custom')]

    def _get_employee_booking_info(self, booking_profile):
        if not request.env.user.employee_id:
            return {}
        params = {'filter_employee_ids': str(request.env.user.employee_id.ids)}
        calendar_url = url_join(booking_profile.get_base_url(), '/booking/')
        profile_url = url_join(calendar_url, slug(booking_profile))
        profile_resource_url = "%s?%s" % (profile_url, url_encode(params))
        return {
            'id': booking_profile.id,
            'url': profile_resource_url
        }
