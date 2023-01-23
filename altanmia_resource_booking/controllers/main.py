# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from babel.dates import format_datetime, format_date
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import pytz
from odoo.fields import Command
from werkzeug.urls import url_encode
from werkzeug.exceptions import Forbidden, NotFound

from odoo import fields, http, SUPERUSER_ID, tools, _
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.osv import expression
from odoo.tools import html2plaintext, is_html_empty, plaintext2html, DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools.misc import get_lang
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.base.models.ir_ui_view import keep_query
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.payment.controllers import portal as payment_portal
_logger = logging.getLogger(__name__)

class Booking(http.Controller):

    # ----------------------------------------------------------
    # Appointment HTTP Routes
    # ----------------------------------------------------------

    @http.route([
        '/booking',
        '/booking/page/<int:page>',
    ], type='http', auth="public", website=True, sitemap=True)
    def booking_profiles_list(self, page=1, **kwargs):
        """
        Display the appointments to choose (the display depends of a custom option called 'Card Design')

        :param page: the page number displayed when the appointments are organized by cards

        A param filter_book_profile_ids can be passed to display a define selection of appointments types.
        This param is propagated through templates to allow people to go back with the initial appointment
        types filter selection
        """
        return request.render('altanmia_resource_booking.booking_profiles_list_layout',
                              self._prepare_booking_list_data(**kwargs))

    @http.route([
        '/booking/<model("tanmia.booking.book.profile"):book>/multi',
    ], type='json', auth="public", website=True, sitemap=True)
    def multi_booking_profiles(self, book, filter_booking_ids=None, timezone=None, state=False, **kwargs):
        """
        Display the appointments to choose (the display depends of a custom option called 'Card Design')

        :param page: the page number displayed when the appointments are organized by cards

        A param filter_book_profile_ids can be passed to display a define selection of appointments types.
        This param is propagated through templates to allow people to go back with the initial appointment
        types filter selection
        """
        book = book.sudo()
        request.session['timezone'] = timezone or book.appointment_tz
        try:
            filter_booking_ids = json.loads(filter_booking_ids) if filter_booking_ids else []
        except json.decoder.JSONDecodeError:
            raise ValueError()

        if book.assign_method == 'chosen' and not filter_booking_ids:
            suggested = book.employee_ids if book.resource_type == 'person' else book.places_ids
        else:
            suggested = book.employee_ids.filtered(lambda emp: emp.id in filter_booking_ids) \
                if book.resource_type == 'person' else book.places_ids

        # Keep retro compatibility with the the old personal link ?employee_id=
        employee_id = kwargs.get('employee_id')

        if not suggested and employee_id and \
                (int(employee_id) in book.employee_ids.ids or int(employee_id) in book.places_ids.ids):
            suggested = request.env['hr.employee'].sudo().browse(int(employee_id))

        default_employee = suggested[0] if suggested else request.env['hr.employee']
        slots = book._get_booking_slots(request.session['timezone'], default_employee)

        self.clear_booking_order()

        return request.env.ref('altanmia_resource_booking.calendar')._render({
            'booking_profile': book,
            'slots': slots,
        })

    @http.route([
        '/booking/<model("tanmia.booking.book.profile"):book>',
    ], type='http', auth="public", website=True, sitemap=True)
    def booking_profile(self, book, filter_booking_ids=None, timezone=None, state=False, **kwargs):
        """
        Render the appointment information alongside the calendar for the slot selection

        :param appointment_type: the appointment type we are currently on
        :param filter_employee_ids: the employees that will be displayed for the appointment registration, if not given
            all employees set for the appointment type are used
        :param timezone: the timezone used to display the available slots
        :param state: the type of message that will be displayed in case of an error/info. Possible values:
            - cancel: Info message to confirm that an appointment has been canceled
            - failed-employee: Error message displayed when the slot has been taken while doing the registration
            - failed-partner: Info message displayed when the partner has already an event in the time slot selected
        """
        book = book.sudo()
        request.session['timezone'] = timezone or book.appointment_tz
        try:
            filter_booking_ids = json.loads(filter_booking_ids) if filter_booking_ids else []
        except json.decoder.JSONDecodeError:
            raise ValueError()

        if book.assign_method == 'chosen' and not filter_booking_ids:
            suggested = book.employee_ids if book.resource_type == 'person' else book.places_ids
        else:#.filtered(lambda emp: emp.id in filter_booking_ids) \
            suggested = book.employee_ids \
                if book.resource_type == 'person' else book.places_ids

        # Keep retro compatibility with the the old personal link ?employee_id=
        employee_id = kwargs.get('employee_id')

        if not suggested and employee_id and \
                (int(employee_id) in book.employee_ids.ids or int(employee_id) in book.places_ids.ids):
            suggested = request.env['hr.employee'].sudo().browse(int(employee_id))

        default_employee = suggested[0] if suggested else request.env['hr.employee']
        slots = book._get_booking_slots(request.session['timezone'], default_employee)
        formated_days = [
            format_date(fields.Date.from_string('2021-03-0%s' % str(day + 1)), "EEE", get_lang(request.env).code) for
            day in range(7)]

        self.clear_booking_order()

        return request.render("altanmia_resource_booking.booking_calendar", {
            'booking_profile': book,
            'suggested_resources': suggested,
            'main_object': book,
            'timezone': request.session['timezone'],  # bw compatibility
            'slots': slots,
            'state': state,
            'filter_book_profile_ids': kwargs.get('filter_book_profile_ids'),
            'formated_days': formated_days,
        })

    def clear_booking_order(self):
        order = request.website.booking_get_order()
        if order and order.state == 'draft':
            for line in order.order_line:
                line.unlink()

    @http.route('/booking/max', type='json', auth="public")
    def Booking_max_number(self, **post):
        max = int(request.env['ir.config_parameter'].sudo().get_param('max_multi_booking_number'))
        return max if max and max > 1 else 10

    @http.route([
        '/booking/<model("tanmia.booking.book.profile"):book>/profile',
    ], type='http', auth='public', website=True, sitemap=True)
    def show_booking_profile(self, book, filter_employee_ids=None, timezone=None, failed=False, **kwargs):
        return request.redirect('/booking/%s?%s' % (slug(book), keep_query('*')))

    def _prepare_calendar_values(self, book, date_start, date_end, duration, description, name, resource, partner):
        """
        prepares all values needed to create a new calendar.event
        """
        #categ_id = request.env.ref('altanmia_resource_booking.calendar_event_type_data_booking')
        alarm_ids = book.reminder_ids and [(6, 0, book.reminder_ids.ids)] or []
        partner_ids = list(
            set([resource.partner_id.id] + [partner.id])) if book.resource_type == 'person' else [partner.id]
        return {
            'name': _('%s booking_in %s', book.name, name),
            'start': date_start.strftime(dtf),
            # FIXME master
            # we override here start_date(time) value because they are not properly
            # recomputed due to ugly overrides in event.calendar (reccurrencies suck!)
            #     (fixing them in stable is a pita as it requires a good rewrite of the
            #      calendar engine)
            'start_date': date_start.strftime(dtf),
            'stop': date_end.strftime(dtf),
            'active': False,
            'allday': False,
            'duration': duration,
            'description': description,
            'alarm_ids': alarm_ids,
            'location': book.location,
            'partner_ids': [(4, pid, False) for pid in partner_ids],
            'partner_id': partner.id,
            'categ_ids': [],
            'book_profile_id': book.id,
            'place_id': None if book.resource_type == 'person' else resource.id,
            'user_id': resource.id if book.resource_type == 'person' else None,
        }


    @http.route(['/booking/view/<string:access_token>'], type='http', auth="public", website=True)
    def calendar_booking_view(self, access_token, partner_id, state=False, **kwargs):
        """
        Render the validation of an appointment and display a summary of it

        :param access_token: the access_token of the event linked to the appointment
        :param state: allow to display an info message, possible values:
            - new: Info message displayed when the appointment has been correctly created
            - no-cancel: Info message displayed when an appointment can no longer be canceled
        """
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event:
            return request.not_found()
        timezone = request.session.get('timezone')
        if not timezone:
            timezone = request.env.context.get('tz') or event.book_profile_id.appointment_tz or event.partner_ids and \
                       event.partner_ids[0].tz or event.user_id.tz or 'UTC'
            request.session['timezone'] = timezone
        tz_session = pytz.timezone(timezone)

        date_start_suffix = ""
        format_func = format_datetime
        if not event.allday:
            url_date_start = fields.Datetime.from_string(event.start).strftime('%Y%m%dT%H%M%SZ')
            url_date_stop = fields.Datetime.from_string(event.stop).strftime('%Y%m%dT%H%M%SZ')
            date_start = fields.Datetime.from_string(event.start).replace(tzinfo=pytz.utc).astimezone(tz_session)
        else:
            url_date_start = url_date_stop = fields.Date.from_string(event.start_date).strftime('%Y%m%d')
            date_start = fields.Date.from_string(event.start_date)
            format_func = format_date
            date_start_suffix = _(', All Day')

        locale = get_lang(request.env).code
        day_name = format_func(date_start, 'EEE', locale=locale)
        date_start = day_name + ' ' + format_func(date_start, locale=locale) + date_start_suffix
        # convert_online_event_desc_to_text method for correct data formatting in external calendars
        details = event.book_profile_id and event.book_profile_id.message_confirmation or event.convert_online_event_desc_to_text(
            event.description) or ''
        params = {
            'action': 'TEMPLATE',
            'text': event.name,
            'dates': url_date_start + '/' + url_date_stop,
            'details': html2plaintext(details.encode('utf-8'))
        }
        if event.location:
            params.update(location=event.location.replace('\n', ' '))
        encoded_params = url_encode(params)
        google_url = 'https://www.google.com/calendar/render?' + encoded_params

        return request.render("altanmia_resource_booking.appointment_validated", {
            'event': event,
            'datetime_start': date_start,
            'google_url': google_url,
            'state': state,
            'partner_id': partner_id,
            'is_html_empty': is_html_empty,
        })



    @http.route([
        '/booking/cancel/<string:access_token>',
        '/booking/<string:access_token>/cancel'
    ], type='http', auth="public", website=True)
    def calendar_booking_cancel(self, access_token, partner_id, **kwargs):
        """
            Route to cancel an appointment event, this route is linked to a button in the validation page
        """
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        appointment_type = event.book_profile_id
        if not event:
            return request.not_found()
        if fields.Datetime.from_string(
                event.allday and event.start_date or event.start) < datetime.now() + relativedelta(
            hours=event.book_profile_id.min_cancellation_hours):
            return request.redirect('/calendar/view/' + access_token + '?state=no-cancel&partner_id=%s' % partner_id)
        event.sudo().action_cancel_meeting([int(partner_id)])
        return request.redirect('/calendar/%s/appointment?state=cancel' % slug(appointment_type))

    @http.route(['/booking/ics/<string:access_token>.ics'], type='http', auth="public", website=True)
    def calendar_booking_ics(self, access_token, **kwargs):
        """
            Route to add the appointment event in a iCal/Outlook calendar
        """
        event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not event or not event.attendee_ids:
            return request.not_found()
        files = event._get_ics_file()
        content = files[event.id]
        return request.make_response(content, [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Length', len(content)),
            ('Content-Disposition', 'attachment; filename=Booking.ics')
        ])

    # ----------------------------------------------------------
    # Booking JSON Routes
    # ----------------------------------------------------------

    @http.route(['/booking/<int:book_profile_id>/get_message_intro'], type="json", auth="public", methods=['POST'],
                website=True)
    def get_booking_message_intro(self, book_profile_id, **kwargs):
        booking_profile = request.env['tanmia.booking.book.profile'].browse(int(book_profile_id)).exists()
        if not booking_profile:
            raise NotFound()

        return booking_profile.message_intro or ''

    @http.route(['/booking/<int:book_profile_id>/update_available_slots'], type="json", auth="public", website=True)
    def calendar_booking_update_available_slots(self, book_profile_id, resource_id=None, timezone=None, **kwargs):
        """
            Route called when the employee or the timezone is modified to adapt the possible slots accordingly
        """
        booking_proifle = request.env['tanmia.booking.book.profile'].browse(int(book_profile_id))

        request.session['timezone'] = timezone or booking_proifle.appointment_tz
        resource = None
        if resource_id:
            resource = request.env['hr.employee'].sudo().browse(int(resource_id)) \
                if booking_proifle.resource_type == 'person' else request.env['account.asset'].sudo().browse(
                int(resource_id))

        slots = booking_proifle.sudo()._get_booking_slots(request.session['timezone'], resource)

        return request.env.ref('altanmia_resource_booking.calendar')._render({
            'booking_profile': booking_proifle,
            'slots': slots,
        })

    # ----------------------------------------------------------
    # Utility Methods
    # ----------------------------------------------------------

    def _booking_base_domain(self, filter_book_profile_ids):
        domain = [('category', '=', 'website')]

        if filter_book_profile_ids:
            domain = expression.AND([domain, [('id', 'in', json.loads(filter_book_profile_ids))]])
        else:
            country = self._get_customer_country()
            if country:
                country_domain = ['|', ('country_ids', '=', False), ('country_ids', 'in', [country.id])]
                domain = expression.AND([domain, country_domain])

        return domain

    def _prepare_booking_list_data(self, **kwargs):
        """
            Compute specific data for the list layout.
        """
        domain = self._booking_base_domain(kwargs.get('filter_book_profile_ids'))

        booking_profiles = request.env['tanmia.booking.book.profile'].search(domain)
        return {
            'booking_profiles': booking_profiles,
        }

    def _get_customer_partner(self):
        partner = request.env['res.partner']
        if not request.env.user._is_public():
            partner = request.env.user.partner_id
        return partner

    def _get_customer_country(self):
        """
            Find the country from the geoip lib or fallback on the user or the visitor
        """
        country_code = request.session.geoip and request.session.geoip.get('country_code')
        country = request.env['res.country']
        if country_code:
            country = country.search([('code', '=', country_code)])
        if not country:
            country = request.env.user.country_id if not request.env.user._is_public() else country
        return country

    def order_2_return_dict(self, order):
        """ Returns the tracking_cart dict of the order for Google analytics basically defined to be inherited """
        return {
            'transaction_id': order.id,
            'affiliation': order.company_id.name,
            'value': order.amount_total,
            'tax': order.amount_tax,
            'currency': order.currency_id.name,
            'items': self.order_lines_2_google_api(order.order_line),
        }

    def order_lines_2_google_api(self, order_lines):
        """ Transforms a list of order lines into a dict for google analytics """
        ret = []
        for line in order_lines:
            product = line.product_id
            ret.append({
                'item_id': product.barcode or product.id,
                'item_name': product.name or '-',
                'item_category': product.categ_id.name or '-',
                'price': line.price_unit,
                'quantity': line.product_uom_qty,
            })
        return ret

    def check_resource_availability(self, book, resource_id, date_start, date_end):
        resource, available ,state= book.check_booking_availability(resource_id, date_start, date_end)
        redirect = None
        if not available:
            redirect = request.redirect('/booking/%s/profile?state=%s' % (slug(book),state))
        return resource, redirect

    @http.route(['/booking/<model("tanmia.booking.book.profile"):book>/info'], type='http', auth="public", website=True, sitemap=False)
    def booking_info(self, book, dates, **post):
        """
        resource_id: could be employee or place
        Main cart management + abandoned cart revival
        access_token: Abandoned cart SO access token
        revive: Revival method when abandoned cart. Can be 'merge' or 'squash'
        """
        # get customer

        dates = json.loads(dates)
        timezone = request.session['timezone'] or book.appointment_tz
        tz_session = pytz.timezone(timezone)
        post['product'] = book.as_product.id

        # create booking card
        # if order not exist force create one
        booking_order = request.website.booking_get_order(force_create=1)

        # if order is not draft
        if booking_order and booking_order.state != 'draft':
            booking_order = None
            request.session['booking_order_id'] = False
            booking_order = request.website.booking_get_order(force_create=1)

        # if order is sale order not booking order
        if not booking_order.booking_order:
            booking_order = None
            request.session['booking_order_id'] = False
            booking_order = request.website.booking_get_order(force_create=1)

        events = []

        for d in dates:
            date_time = d['datetime']
            resource_id = d['employee_id']
            date_start = tz_session.localize(fields.Datetime.from_string(date_time)).astimezone(pytz.utc)
            duration = float(d['duration'])
            date_end = date_start + relativedelta(hours=duration)

            # check availability of the resource again (in case someone else booked while the client was entering the form)
            resource, redirect = self.check_resource_availability(book, resource_id, date_start, date_end)
            if redirect:
                return redirect

            user_id = resource.user_id if book.resource_type == 'person' else None
            place_id = None if book.resource_type == 'person' else resource
            allowed_company_ids = user_id.company_ids.ids if user_id else [place_id.company_id.id]
            event = request.env['calendar.event'].with_context(
                mail_notify_author=True,
                allowed_company_ids=allowed_company_ids,
            ).sudo().create(
                self._prepare_calendar_values(
                    book,
                    date_start,
                    date_end,
                    duration,
                    'Booking Description',
                    'Booking Name',
                    user_id if user_id else place_id,
                    booking_order.partner_id)
            )
            event.attendee_ids.write({'state': 'accepted'})

            events.append(event)
        
        
        # i don't know how, but this line to delete all lines from order
        booking_order.write({
            'order_line': [(5,0,0)],
        })
        booking_order.add_date(dates=events,kwargs=post)
        request.session['booking_profile_id'] = book.id
        return request.redirect('/booking/checkout')

    # ------------------------------------------------------
    # Checkout
    # ------------------------------------------------------

    def checkout_check_address(self, order):

        billing_fields_required = self._get_mandatory_fields_billing(order.partner_id.country_id.id)
        if not all(order.partner_id.read(billing_fields_required)[0].values()):
            return request.redirect('/booking/address?partner_id=%d' % order.partner_id.id)

        shipping_fields_required = self._get_mandatory_fields_shipping(order.partner_shipping_id.country_id.id)
        if not all(order.partner_shipping_id.read(shipping_fields_required)[0].values()):
            return request.redirect('/booking/address?partner_id=%d' % order.partner_shipping_id.id)

    def checkout_redirection(self, order):
        # must have a draft sales order with lines at this point, otherwise reset
        if not order or order.state != 'draft':
            request.session['booking_order_id'] = None
            request.session['booking_transaction_id'] = None
            return request.redirect('/booking')

        if order and not order.order_line:
            return request.redirect('/booking')

        for line in order.order_line:
           for event in line.booking_events:
               # event = line.booking_event
               book = event.book_profile_id
               timezone = request.session['timezone'] or book.appointment_tz
               tz_session = pytz.timezone(timezone)
               resource = request.env['hr.employee'].sudo().with_user(
                   event.user_id.id) if book.resource_type == 'person' else event.place_id

               start = tz_session.localize(event.start).astimezone(pytz.utc)
               end = tz_session.localize(event.stop).astimezone(pytz.utc)

               # _, redirect = self.check_resource_availability(book, resource, start, end)
               # if redirect:
               #     return redirect

        # if transaction pending / done: redirect to confirmation
        tx = request.env.context.get('website_booking_transaction')
        if tx and tx.state != 'draft':
            return request.redirect('/booking/payment/confirmation/%s' % order.id)

    def checkout_values(self, **kw):
        order = request.website.booking_get_order(force_create=1)
        shippings = []
        if order.partner_id != request.website.user_id.sudo().partner_id:
            Partner = order.partner_id.with_context(show_address=1).sudo()
            shippings = Partner.search([
                ("id", "child_of", order.partner_id.commercial_partner_id.ids),
                '|', ("type", "in", ["delivery", "other"]), ("id", "=", order.partner_id.commercial_partner_id.id)
            ], order='id desc')
            if shippings:
                if kw.get('partner_id') or 'use_billing' in kw:
                    if 'use_billing' in kw:
                        partner_id = order.partner_id.id
                    else:
                        partner_id = int(kw.get('partner_id'))
                    if partner_id in shippings.mapped('id'):
                        order.partner_shipping_id = partner_id

        values = {
            'order': order,
            'shippings': shippings,
            'only_services': True
        }
        return values

    def _get_mandatory_fields_billing(self, country_id=False):
        req = ["name", "email", "street", "city", "country_id"]
        if country_id:
            country = request.env['res.country'].browse(country_id)
            if country.state_required:
                req += ['state_id']
            if country.zip_required:
                req += ['zip']
        return req

    def _get_mandatory_fields_shipping(self, country_id=False):
        req = ["name", "street", "city", "country_id"]
        if country_id:
            country = request.env['res.country'].browse(country_id)
            if country.state_required:
                req += ['state_id']
            if country.zip_required:
                req += ['zip']
        return req

    def checkout_form_validate(self, mode, all_form_values, data):
        # mode: tuple ('new|edit', 'billing|shipping')
        # all_form_values: all values before preprocess
        # data: values after preprocess
        error = dict()
        error_message = []

        # Required fields from form
        required_fields = [f for f in (all_form_values.get('field_required') or '').split(',') if f]

        # Required fields from mandatory field function
        country_id = int(data.get('country_id', False))
        required_fields += mode[1] == 'shipping' and self._get_mandatory_fields_shipping(country_id) or self._get_mandatory_fields_billing(country_id)

        # error message for empty required fields
        for field_name in required_fields:
            if not data.get(field_name):
                error[field_name] = 'missing'

        # email validation
        if data.get('email') and not tools.single_email_re.match(data.get('email')):
            error["email"] = 'error'
            error_message.append(_('Invalid Email! Please enter a valid email address.'))

        # vat validation
        Partner = request.env['res.partner']
        if data.get("vat") and hasattr(Partner, "check_vat"):
            if country_id:
                data["vat"] = Partner.fix_eu_vat_number(country_id, data.get("vat"))
            partner_dummy = Partner.new(self._get_vat_validation_fields(data))
            try:
                partner_dummy.check_vat()
            except ValidationError as exception:
                error["vat"] = 'error'
                error_message.append(exception.args[0])

        if [err for err in error.values() if err == 'missing']:
            error_message.append(_('Some required fields are empty.'))

        return error, error_message

    def _get_vat_validation_fields(self, data):
        return {
            'vat': data['vat'],
            'country_id': int(data['country_id']) if data.get('country_id') else False,
        }

    def _checkout_form_save(self, mode, checkout, all_values):
        Partner = request.env['res.partner']
        if mode[0] == 'new':
            partner_id = Partner.sudo().with_context(tracking_disable=True).create(checkout).id
        elif mode[0] == 'edit':
            partner_id = int(all_values.get('partner_id', 0))
            if partner_id:
                # double check
                order = request.website.booking_get_order()
                shippings = Partner.sudo().search([("id", "child_of", order.partner_id.commercial_partner_id.ids)])
                if partner_id not in shippings.mapped('id') and partner_id != order.partner_id.id:
                    return Forbidden()
                Partner.browse(partner_id).sudo().write(checkout)

        return partner_id

    def values_preprocess(self, order, mode, values):
        # Convert the values for many2one fields to integer since they are used as IDs
        partner_fields = request.env['res.partner']._fields
        return {
            k: (bool(v) and int(v)) if k in partner_fields and partner_fields[k].type == 'many2one' else v
            for k, v in values.items()
        }

    def values_postprocess(self, order, mode, values, errors, error_msg):
        new_values = {}
        authorized_fields = request.env['ir.model']._get('res.partner')._get_form_writable_fields()
        for k, v in values.items():
            # don't drop empty value, it could be a field to reset
            if k in authorized_fields and v is not None:
                new_values[k] = v
            else:  # DEBUG ONLY
                if k not in ('field_required', 'partner_id', 'callback', 'submitted'): # classic case
                    _logger.debug("website_sale postprocess: %s value has been dropped (empty or not writable)" % k)

        if request.website.specific_user_account:
            new_values['website_id'] = request.website.id

        if mode[0] == 'new':
            new_values['company_id'] = request.website.company_id.id
            new_values['team_id'] = request.website.salesteam_id and request.website.salesteam_id.id
            new_values['user_id'] = request.website.salesperson_id.id

        lang = request.lang.code if request.lang.code in request.website.mapped('language_ids.code') else None
        if lang:
            new_values['lang'] = lang
        if mode == ('edit', 'billing') and order.partner_id.type == 'contact':
            new_values['type'] = 'other'
        if mode[1] == 'shipping':
            new_values['parent_id'] = order.partner_id.commercial_partner_id.id
            new_values['type'] = 'delivery'

        return new_values, errors, error_msg

    @http.route(['/booking/address'], type='http', methods=['GET', 'POST'], auth="public", website=True, sitemap=False)
    def address(self, **kw):
        Partner = request.env['res.partner'].with_context(show_address=1).sudo()
        order = request.website.booking_get_order()

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        mode = (False, False)
        can_edit_vat = False
        values, errors = {}, {}

        partner_id = int(kw.get('partner_id', -1))

        # IF PUBLIC ORDER
        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            mode = ('new', 'billing')
            can_edit_vat = True
        # IF ORDER LINKED TO A PARTNER
        else:
            if partner_id > 0:
                if partner_id == order.partner_id.id:
                    mode = ('edit', 'billing')
                    can_edit_vat = order.partner_id.can_edit_vat()
                else:
                    shippings = Partner.search([('id', 'child_of', order.partner_id.commercial_partner_id.ids)])
                    if order.partner_id.commercial_partner_id.id == partner_id:
                        mode = ('new', 'shipping')
                        partner_id = -1
                    elif partner_id in shippings.mapped('id'):
                        mode = ('edit', 'shipping')
                    else:
                        return Forbidden()
                if mode and partner_id != -1:
                    values = Partner.browse(partner_id)
            elif partner_id == -1:
                mode = ('new', 'shipping')
            else: # no mode - refresh without post?
                return request.redirect('/booking/checkout')

        # IF POSTED
        if 'submitted' in kw and request.httprequest.method == "POST":
            pre_values = self.values_preprocess(order, mode, kw)
            errors, error_msg = self.checkout_form_validate(mode, kw, pre_values)
            post, errors, error_msg = self.values_postprocess(order, mode, pre_values, errors, error_msg)

            if errors:
                errors['error_message'] = error_msg
                values = kw
            else:
                partner_id = self._checkout_form_save(mode, post, kw)
                if mode[1] == 'billing':
                    order.partner_id = partner_id
                    order.with_context(not_self_saleperson=True).onchange_partner_id()
                    # This is the *only* thing that the front end user will see/edit anyway when choosing billing address
                    order.partner_invoice_id = partner_id
                    if not kw.get('use_same'):
                        kw['callback'] = kw.get('callback') or \
                            (not order.only_services and (mode[0] == 'edit' and '/booking/checkout' or '/booking/address'))
                elif mode[1] == 'shipping':
                    order.partner_shipping_id = partner_id

                # TDE FIXME: don't ever do this
                # -> TDE: you are the guy that did what we should never do in commit e6f038a
                order.message_partner_ids = [(4, partner_id), (3, request.website.partner_id.id)]
                if not errors:
                    return request.redirect(kw.get('callback') or '/booking/confirm_order')

        render_values = {
            'website_booking_order': order,
            'partner_id': partner_id,
            'mode': mode,
            'checkout': values,
            'can_edit_vat': can_edit_vat,
            'error': errors,
            'callback': kw.get('callback'),
            'only_services': order and order.only_services,
        }

        render_values.update({'website_booking_order': order})

        render_values.update(self._get_country_related_render_values(kw, render_values))
        render_values.update({'book_profile_id': request.session['booking_profile_id']})
        return request.render("altanmia_resource_booking.address", render_values)

    def _get_country_related_render_values(self, kw, render_values):
        '''
        This method provides fields related to the country to render the website sale form
        '''
        values = render_values['checkout']
        mode = render_values['mode']
        order = render_values['website_booking_order']

        def_country_id = order.partner_id.country_id
        # IF PUBLIC ORDER
        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            country_code = request.session['geoip'].get('country_code')
            if country_code:
                def_country_id = request.env['res.country'].search([('code', '=', country_code)], limit=1)
            else:
                def_country_id = request.website.user_id.sudo().country_id

        country = 'country_id' in values and values['country_id'] != '' and request.env['res.country'].browse(int(values['country_id']))
        country = country and country.exists() or def_country_id

        res = {
            'country': country,
            'country_states': country.get_website_sale_states(mode=mode[1]),
            'countries': country.get_website_sale_countries(mode=mode[1]),
        }
        return res

    @http.route(['/booking/checkout'], type='http', auth="public", website=True, sitemap=False)
    def checkout(self, **post):
        #request.env['calendar.event'].with_context(active_test=False)
        order = request.website.booking_get_order()

        for line in order.order_line:
            print("line", line.booking_events)

        redirection = self.checkout_redirection(order)
        if redirection:
            return redirection

        if order.partner_id.id == request.website.user_id.sudo().partner_id.id:
            return request.redirect('/booking/address')

        redirection = self.checkout_check_address(order)
        if redirection:
            return redirection

        values = self.checkout_values(**post)

        if post.get('express'):
            return request.redirect('/booking/confirm_order')

        values.update({'website_booking_order': order})
        values.update({'book_profile_id': request.session['booking_profile_id']})

        # Avoid useless rendering if called in ajax
        if post.get('xhr'):
            return 'ok'

        return request.render("altanmia_resource_booking.checkout", values)

    @http.route(['/booking/confirm_order'], type='http', auth="public", website=True, sitemap=False)
    def confirm_order(self, **post):
        order = request.website.booking_get_order()

        redirection = self.checkout_redirection(order) or self.checkout_check_address(order)
        if redirection:
            return redirection

        order.onchange_partner_shipping_id()
        order.order_line._compute_tax_id()
        request.session['booking_last_order_id'] = order.id
        request.website.booking_get_order(update_pricelist=True)
        extra_step = request.website.viewref('website_sale.extra_info_option')
        if extra_step.active:
            return request.redirect("/booking/extra_info")
        return request.redirect("/booking/payment")

    # ------------------------------------------------------
    # Payment
    # ------------------------------------------------------

    def _get_shop_payment_values(self, order, **kwargs):
        logged_in = not request.env.user._is_public()
        acquirers_sudo = request.env['payment.acquirer'].sudo()._get_compatible_acquirers(
            order.company_id.id,
            order.partner_id.id,
            currency_id=order.currency_id.id,
            sale_order_id=order.id,
            website_id=request.website.id,
        )  # In sudo mode to read the fields of acquirers, order and partner (if not logged in)
        tokens = request.env['payment.token'].search(
            [('acquirer_id', 'in', acquirers_sudo.ids), ('partner_id', '=', order.partner_id.id)]
        ) if logged_in else request.env['payment.token']
        fees_by_acquirer = {
            acq_sudo: acq_sudo._compute_fees(
                order.amount_total, order.currency_id, order.partner_id.country_id
            ) for acq_sudo in acquirers_sudo.filtered('fees_active')
        }
        # Prevent public partner from saving payment methods but force it for logged in partners
        # buying subscription products
        show_tokenize_input = logged_in \
            and not request.env['payment.acquirer'].sudo()._is_tokenization_required(
                sale_order_id=order.id
            )
        return {
            'website_booking_order': order,
            'errors': [],
            'partner': order.partner_id,
            'order': order,
            'payment_action_id': request.env.ref('payment.action_payment_acquirer').id,
            # Payment form common (checkout and manage) values
            'acquirers': acquirers_sudo,
            'tokens': tokens,
            'fees_by_acquirer': fees_by_acquirer,
            'show_tokenize_input': show_tokenize_input,
            'amount': order.amount_total,
            'currency': order.currency_id,
            'partner_id': order.partner_id.id,
            'access_token': order._portal_ensure_token(),
            'transaction_route': f'/booking/payment/transaction/{order.id}',
            'landing_route': '/booking/payment/validate',
        }

    @http.route('/booking/payment', type='http', auth='public', website=True, sitemap=False)
    def shop_payment(self, **post):
        """ Payment step. This page proposes several payment means based on available
        payment.acquirer. State at this point :

         - a draft sales order with lines; otherwise, clean context / session and
           back to the shop
         - no transaction in context / session, or only a draft one, if the customer
           did go to a payment.acquirer website but closed the tab without
           paying / canceling
        """
        order = request.website.booking_get_order()
        redirection = self.checkout_redirection(order) or self.checkout_check_address(order)
        if redirection:
            return redirection

        render_values = self._get_shop_payment_values(order, **post)
        render_values['only_services'] = order and order.only_services or False
        render_values.update({'book_profile_id': request.session['booking_profile_id']})

        if render_values['errors']:
            render_values.pop('acquirers', '')
            render_values.pop('tokens', '')

        return request.render("altanmia_resource_booking.payment", render_values)

    @http.route('/booking/payment/get_status/<int:booking_order_id>', type='json', auth="public", website=True)
    def shop_payment_get_status(self, booking_order_id, **post):
        order = request.env['sale.order'].sudo().browse(booking_order_id).exists()
        if order.id != request.session.get('booking_last_order_id'):
            # either something went wrong or the session is unbound
            # prevent recalling every 3rd of a second in the JS widget
            return {}

        return {
            'recall': order.get_portal_last_book_transaction().state == 'pending',
            'message': request.env['ir.ui.view']._render_template("altanmia_resource_booking.payment_confirmation_status", {
                'order': order
            })
        }

    @http.route('/booking/payment/validate', type='http', auth="public", website=True, sitemap=False)
    def shop_payment_validate(self, transaction_id=None, booking_order_id=None, **post):
        """ Method that should be called by the server when receiving an update
        for a transaction. State at this point :

         - UDPATE ME
        """
        if booking_order_id is None:
            order = request.website.booking_get_order()
        else:
            order = request.env['sale.order'].sudo().browse(booking_order_id)
            assert order.id == request.session.get('booking_last_order_id')

        if transaction_id:
            tx = request.env['payment.transaction'].sudo().browse(transaction_id)
            assert tx in order.book_transaction_ids()
        elif order:
            tx = order.get_portal_last_book_transaction()
        else:
            tx = None

        if not order or (order.amount_total and not tx):
            return request.redirect('/booking')

        if order and not order.amount_total and not tx:
            order.with_context(send_email=True).action_confirm()
            return request.redirect(order.get_portal_url())

        # clean context and session, then redirect to the confirmation page
        request.website.sale_reset()
        if tx and tx.state == 'draft':
            return request.redirect('/booking')

        PaymentPostProcessing.remove_transactions(tx)
        return request.redirect('/booking/confirmation')

    @http.route(['/booking/confirmation'], type='http', auth="public", website=True, sitemap=False)
    def shop_payment_confirmation(self, **post):
        """ End of checkout process controller. Confirmation is basically seing
        the status of a sale.order. State at this point :

         - should not have any context / session info: clean them
         - take a sale.order id, because we request a sale.order and are not
           session dependant anymore
        """
        booking_order_id = request.session.get('booking_last_order_id')
        if booking_order_id:
            order = request.env['sale.order'].sudo().browse(booking_order_id)
            order.make_reservation()
            return request.render("altanmia_resource_booking.confirmation", {
                'order': order,
                'order_tracking_info': self.order_2_return_dict(order),
            })
        else:
            return request.redirect('/booking')

    @http.route(['/booking/print'], type='http', auth="public", website=True, sitemap=False)
    def print_saleorder(self, **kwargs):
        booking_order_id = request.session.get('booking_last_order_id')
        if booking_order_id:
            pdf, _ = request.env.ref('sale.action_report_saleorder').with_user(SUPERUSER_ID)._render_qweb_pdf([booking_order_id])
            pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', u'%s' % len(pdf))]
            return request.make_response(pdf, headers=pdfhttpheaders)
        else:
            return request.redirect('/booking')


class PaymentPortal(payment_portal.PaymentPortal):

    @http.route(
        '/booking/payment/transaction/<int:order_id>', type='json', auth='public', website=True
    )
    def booking_payment_transaction(self, order_id, access_token, **kwargs):
        """ Create a draft transaction and return its processing values.

        :param int order_id: The sales order to pay, as a `sale.order` id
        :param str access_token: The access token used to authenticate the request
        :param dict kwargs: Locally unused data passed to `_create_transaction`
        :return: The mandatory values for the processing of the transaction
        :rtype: dict
        :raise: ValidationError if the invoice id or the access token is invalid
        """

        # Check the order id and the access token
        try:
            self._document_check_access('sale.order', order_id, access_token)
        except MissingError as error:
            raise error
        except AccessError:
            raise ValidationError("The access token is invalid.")

        kwargs.update({
            'reference_prefix': None,  # Allow the reference to be computed based on the order
            'booking_order_id': order_id,  # Include the SO to allow Subscriptions to tokenize the tx
        })
        kwargs.pop('custom_create_values', None)  # Don't allow passing arbitrary create values
        tx_sudo = self._create_transaction(
            custom_create_values={'booking_order_ids': [Command.set([order_id])]}, **kwargs,
        )

        # Store the new transaction into the transaction list and if there's an old one, we remove
        # it until the day the ecommerce supports multiple orders at the same time.
        last_tx_id = request.session.get('__website_booking_last_tx_id')
        last_tx = request.env['payment.transaction'].browse(last_tx_id).sudo().exists()
        if last_tx:
            PaymentPostProcessing.remove_transactions(last_tx)
        request.session['__website_booking_last_tx_id'] = tx_sudo.id

        return tx_sudo._get_processing_values()
