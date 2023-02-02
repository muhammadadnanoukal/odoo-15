# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import calendar as cal
import random
import pytz
from datetime import datetime, timedelta, time, date
from dateutil import rrule
from dateutil.relativedelta import relativedelta
from babel.dates import format_datetime, format_date
from werkzeug.urls import url_join

from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError
from odoo.tools.misc import get_lang
from odoo.addons.base.models.res_partner import _tz_get
from odoo.addons.http_routing.models.ir_http import slug
from odoo.osv.expression import AND
from dateutil.rrule import rrule, rruleset, DAILY, WEEKLY, MONTHLY, YEARLY, MO, TU, WE, TH, FR, SA, SU
from lxml import etree, objectify
from werkzeug.exceptions import Forbidden, NotFound

REPEAT_UNIT = {
    'Weeks': WEEKLY,
    'Months': MONTHLY
}

DAYS = {
    'Monday': MO,
    'Tuesday': TU,
    'Wednesday': WE,
    'Thursday': TH,
    'Friday': FR,
    'Saturday': SA,
    'Sunday': SU,
}

WEEKS = {
    'first': 1,
    'second': 2,
    'third': 3,
    'last': 4,
}

class BookProfile(models.Model):
    _name = "tanmia.booking.book.profile"
    _description = """
    Booking Profile
    ===============
    Tel customer about available booking in our service as book a [studio, stadion, car] 
    or appointment with [doctor, lawyer, consultant] 
    """
    #_inherits = {'product.template': 'profile_tmpl_id'}
    _inherit = ['portal.mixin', 'mail.thread']
    _check_company_auto = True
    _order = "sequence, id"

    @api.model
    def default_get(self, default_fields):
        result = super().default_get(default_fields)
        if 'category' not in default_fields or result.get('category') in ['custom', 'work_hours']:
            if not result.get('name'):
                result['name'] = _("%s - Let's meet", self.env.user.name)
            if (not default_fields or 'employee_ids' in default_fields) and not result.get('employee_ids'):
                if not self.env.user.employee_id:
                    raise ValueError(_("An employee should be set on the current user to create the appointment type"))
                result['employee_ids'] = [Command.set(self.env.user.employee_id.ids)]
        return result

    sequence = fields.Integer('Sequence', default=10)
    name = fields.Char('Profile Name', required=True, translate=True)
    active = fields.Boolean(default=True)
    category = fields.Selection([
        ('website', 'Website'),
        ('custom', 'Custom'),
        ('work_hours', 'Work Hours')
        ], string="Category", default="website",
        help="""Used to define this appointment type's category.
        Can be one of:
            - Website: the default category, the people can access and schedule the appointment with employees from the website
            - Custom: the employee will create and share to an user a custom appointment type with hand-picked time slots
            - Work Hours: a special type of appointment type that is used by one employee and which takes the working hours of this
                employee as availabilities. This one uses recurring slot that englobe the entire week to display all possible slots
                based on its working hours and availabilities""")
    min_schedule_hours = fields.Float('Schedule before (hours)', required=True, default=1.0)
    max_schedule_days = fields.Integer('Schedule not after (days)', required=True, default=15)
    min_cancellation_hours = fields.Float('Cancel Before (hours)', required=True, default=1.0)
    appointment_duration = fields.Float('Appointment Duration', required=True, default=1.0)

    reminder_ids = fields.Many2many('calendar.alarm', string="Reminders")
    location = fields.Char('Location', help="Location of the appointments")
    message_confirmation = fields.Html('Confirmation Message', translate=True)
    message_intro = fields.Html('Introduction Message', translate=True)

    country_ids = fields.Many2many(
        'res.country', 'book_profile_country_rel', string='Restrict Countries',
        help="Keep empty to allow visitors from any country, otherwise you only allow visitors from selected countries")
    question_ids = fields.One2many('tanmia.booking.question', 'book_profile_id', string='Questions', copy=True)

    slot_ids = fields.One2many('tanmia.booking.slot', 'book_profile_id', 'Availabilities', copy=True)
    appointment_tz = fields.Selection(
        _tz_get, string='Timezone', required=True, default=lambda self: self.env.user.tz,
        help="Timezone where appointment take place")
    employee_ids = fields.Many2many('hr.employee', 'book_profile_employee_rel', domain=[('user_id', '!=', False)], string='Employees')

    places_ids = fields.Many2many('account.asset', string='Places',  domain=[('reservable', '=', True)],)

    resource_type = fields.Selection([
        ('person', 'Stuff'),
        ('place', 'Place'),
        ], string="Resource Type", default="person",
        help="""Used to define this reservation  type's .
        Can be one of:
            - Stuff: make an appointment with a staff member
            - Place: booking a room  in a place""")

    capacity = fields.Integer(string="Capacity", compute="compute_places_capacity")

    assign_method = fields.Selection([
        ('random', 'Random'),
        ('chosen', 'Chosen by the Customer')], string='Assignment Method', default='random',
        help="How employees will be assigned to meetings customers book on your website.")
    booking_count = fields.Integer('# Appointments', compute='_compute_booking_count')

    require_payment = fields.Selection([('online', 'Online Payment'), ('cash', 'Cash')],
        help='Request an online payment to or after booking hold in cash.')

    cost = fields.Float(string="Booking Cost")

    as_product = fields.Many2one('product.product', string='Product', help="Considering Booking Profile as Product, to create sale order on booking")
    parent_booking_id = fields.Many2one('tanmia.booking.book.profile', string='Parent', help="")
    children_booking_ids = fields.One2many("tanmia.booking.book.profile", 'parent_booking_id', string="Children", tracking=True)


    available_places_ids = fields.One2many('account.asset', compute='_compute_available_places_ids', string="son places")
    #available_places_ids = fields.Many2many(related='parent_booking_id.places_ids.parts', readonly=True)

    @api.depends('parent_booking_id')
    def _compute_available_places_ids(self):
        for book in self:
            if book.parent_booking_id:
                book.available_places_ids = self.env['account.asset'].sudo().search([
                        ('reservable', '=', True), ('parent', 'in', book.parent_booking_id.places_ids.ids)])
            else:
                book.available_places_ids = self.env['account.asset'].sudo().search([
                    ('reservable', '=', True)])


    def compute_places_capacity(self):
        cap = 0
        for place in self.places_ids:
            cap += place.capacity
        self.capacity = cap

    def _compute_booking_count(self):
        meeting_data = self.env['calendar.event'].read_group([('book_profile_id', 'in', self.ids)], ['book_profile_id'], ['book_profile_id'])
        mapped_data = {m['book_profile_id'][0]: m['book_profile_id_count'] for m in meeting_data}
        for booking_profile in self:
            booking_profile.booking_count = mapped_data.get(booking_profile.id, 0)

    @api.constrains('category', 'employee_ids')
    def _check_employee_configuration(self):
        for booking_profile in self:
            if booking_profile.category != 'website' and len(booking_profile.employee_ids) != 1:
                raise ValidationError(_("This category of appointment type should only have one employee but got %s employees", len(booking_profile.employee_ids)))
            if booking_profile.category == 'work_hours':
                appointment_domain = [('category', '=', 'work_hours'), ('employee_ids', 'in', booking_profile.employee_ids.ids)]
                if booking_profile.ids:
                    appointment_domain = AND([appointment_domain, [('id', 'not in', booking_profile.ids)]])
                if self.search_count(appointment_domain) > 0:
                    raise ValidationError(_("Only one work hours appointment type is allowed for a specific employee."))

    @api.model
    def create(self, values):
        """ We don't want the current user to be follower of all created types """
        return super(BookProfile, self.with_context(mail_create_nosubscribe=True)).create(values)


    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        default['name'] = self.name + _(' (copy)')
        return super(BookProfile, self).copy(default=default)

    def action_calendar_meetings(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("calendar.action_calendar_event")
        bookings = self.env['calendar.event'].search([
            ('book_profile_id', '=', self.id), ('start', '>=', datetime.today()
        )], order='start')
        nbr_bookings_week_later = self.env['calendar.event'].search_count([
            ('book_profile_id', '=', self.id), ('start', '>=', datetime.today() + timedelta(weeks=1))
        ])

        action['context'] = {
            'default_book_profile_id': self.id,
            'search_default_book_profile_id': self.id,
            'default_mode': "month" if nbr_bookings_week_later else "week",
            'initial_date': bookings[0].start if bookings else datetime.today(),
        }
        return action

    def action_share(self):
        self.ensure_one()
        return {
            'name': _('Share Link'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.appointment.share',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_book_profile_ids': self.ids,
                'default_employee_ids': self.employee_ids.filtered(lambda employee: employee.user_id.id == self.env.user.id).ids,
            }
        }

    def check_booking_availability(self, resource_id, date_start, date_end, check_parent=True, check_children=True):

        resource = None
        available = True
        state = ''
        if self.resource_type == 'person':
            resource = self.env['hr.employee'].sudo().browse(int(resource_id)).exists()
            if resource not in self.sudo().employee_ids:
                raise NotFound()

            if resource.user_id and resource.user_id.partner_id:
                if not resource.user_id.partner_id.calendar_verify_availability(date_start, date_end):
                    available = False

        elif self.resource_type == 'place':
            resource = self.env['account.asset'].sudo().browse(int(resource_id)).exists()
            if resource not in self.sudo().places_ids:
                raise NotFound()

            #check parent booking profile
            if check_parent and self.parent_booking_id:
                parent_res = self.get_parent_resource(resource)
                if parent_res:
                    _,available,_ = self.parent_booking_id.check_booking_availability( parent_res.id, date_start, date_end,check_children=False)
                    state = 'failed-parent' if not available else state

            #check children if parent available
            if check_children and available:
                for book in self.children_booking_ids: # for each booking child
                    for res in book.places_ids: # for each place (resource) in this  child
                        if res.parent.id == resource.id: # if this place child of considered resource
                            _, av,_ = book.check_booking_availability(res.id, date_start, date_end, check_parent=False)
                            available = available and av
                            state = 'failed-children' if not available else state
            if available:
                available = resource.calendar_verify_availability(date_start, date_end)
                state = 'failed-employee' if not available else state

        return resource, available, state

    def get_parent_resource(self, child_resource):
        if self.resource_type == "person":
            return
        for res in self.parent_booking_id.places_ids:
            if child_resource.parent.id == res.id:
                return res

    def action_customer_preview(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': url_join(self.get_base_url(), '/booking/%s' % slug(self)),
            'target': 'self',
        }

    # --------------------------------------
    # Slots Generation
    # --------------------------------------

    def _slots_generate(self, first_day, last_day, timezone, reference_date=None):
        """ Generate all appointment slots (in naive UTC, appointment timezone, and given (visitors) timezone)
            between first_day and last_day (datetimes in appointment timezone)

            :return: [ {'slot': slot_record, <timezone>: (date_start, date_end), ...},
                      ... ]
        """
        if not reference_date:
            reference_date = datetime.utcnow()

        def append_slot(day, slot):
            local_start = appt_tz.localize(datetime.combine(day, time(hour=int(slot.start_hour), minute=int(round((slot.start_hour % 1) * 60)))))
            local_end = appt_tz.localize(
                datetime.combine(day, time(hour=int(slot.start_hour), minute=int(round((slot.start_hour % 1) * 60)))) + relativedelta(hours=self.appointment_duration))

            while (local_start.hour + local_start.minute / 60) <= slot.end_hour - self.appointment_duration:
                slots.append({
                    self.appointment_tz: (
                        local_start,
                        local_end,
                    ),
                    timezone: (
                        local_start.astimezone(requested_tz),
                        local_end.astimezone(requested_tz),
                    ),
                    'UTC': (
                        local_start.astimezone(pytz.UTC).replace(tzinfo=None),
                        local_end.astimezone(pytz.UTC).replace(tzinfo=None),
                    ),
                    'slot': slot,
                })
                local_start = local_end
                local_end += relativedelta(hours=self.appointment_duration)
        appt_tz = pytz.timezone(self.appointment_tz)
        requested_tz = pytz.timezone(timezone)

        slots = []
        # We use only the recurring slot if it's not a custom appointment type.
        if self.category != 'custom':

            # Regular recurring slots (not a custom appointment), generate necessary slots using configuration rules
            for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == first_day.isoweekday()):
                if slot.end_hour > first_day.hour + first_day.minute / 60.0:
                    append_slot(first_day.date(), slot)
            slot_weekday = [int(weekday) - 1 for weekday in self.slot_ids.mapped('weekday')]

            for day in rrule(DAILY,
                                dtstart=first_day.date() + timedelta(days=1),
                                until=last_day.date(),
                                byweekday=slot_weekday):

                for slot in self.slot_ids.filtered(lambda x: int(x.weekday) == day.isoweekday()):

                    append_slot(day, slot)

        else:
            # Custom appointment type, we use "unique" slots here that have a defined start/end datetime
            unique_slots = self.slot_ids.filtered(lambda slot: slot.slot_type == 'unique' and slot.end_datetime > reference_date)

            for slot in unique_slots:
                start = slot.start_datetime.astimezone(tz=None)
                end = slot.end_datetime.astimezone(tz=None)
                startUTC = start.astimezone(pytz.UTC).replace(tzinfo=None)
                endUTC = end.astimezone(pytz.UTC).replace(tzinfo=None)
                slots.append({
                    self.appointment_tz: (
                        start.astimezone(appt_tz),
                        end.astimezone(appt_tz),
                    ),
                    timezone: (
                        start.astimezone(requested_tz),
                        end.astimezone(requested_tz),
                    ),
                    'UTC': (
                        startUTC,
                        endUTC,
                    ),
                    'slot': slot,
                })
        return slots

    def _slots_available(self, slots, start_dt, end_dt, employee=None):
        """ Fills the slot structure with an available employee

        :param list slots: slots (list of slot dict), as generated by ``_slots_generate``;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;
        :param <hr.employee> employee: if set, only consider this employee. Otherwise
          consider all employees assigned to this appointment type;

        :return: None but instead update ``slots`` adding ``employee_id`` key
          containing found available employee ID;
        """
        # With context will be used in resource.calendar to force the referential user
        # for work interval computing to the *user linked to the employee*
        if self.resource_type == 'person':
            available_employees = [emp.with_context(tz=emp.user_id.tz) for emp in (employee or self.employee_ids)]
        else:
            available_employees = [emp.with_context(tz=emp.tz) for emp in (employee or self.places_ids)]

        random.shuffle(available_employees)
        available_employees_tz = self.env['hr.employee'].concat(*available_employees) \
            if self.resource_type == 'person' else available_employees

        # fetch value used for availability in batch
        availability_values = self._slot_availability_prepare_values(
            available_employees_tz, start_dt, end_dt
        )
        for slot in slots:
            found_employee = next(
                (potential_employee for potential_employee in available_employees_tz
                 if self._slot_availability_is_employee_available(slot, potential_employee, availability_values)
                ), False
            )
            if found_employee:
                slot['employee_id'] = found_employee

    def _slot_availability_is_employee_available(self, slot, staff_employee, availability_values):
        """ This method verifies if the employee is available on the given slot.
        It checks whether the employee has calendar events clashing and if he
        is working during the slot based on working hours.

        Can be overridden to add custom checks.

        :param dict slot: a slot as generated by ``_slots_generate``;
        :param <hr.employee> staff_employee: employee to check against slot boundaries;
        :param dict availability_values: dict of data used for availability check.
          See ``_slot_availability_prepare_values()`` for more details;

        :return: boolean: is employee available for an appointment for given slot
        """
        is_available = True
        slot_start_dt_utc, slot_end_dt_utc = slot['UTC'][0], slot['UTC'][1]

        # check if the slot in work time of resource
        workhours = availability_values.get('work_schedules')
        resouce = staff_employee.user_partner_id if self.resource_type == 'person' else staff_employee
        if workhours and workhours.get(resouce):
            is_available = self._slot_availability_is_employee_working(
                slot_start_dt_utc, slot_end_dt_utc,
                workhours[resouce]
            )

        if is_available:
            _,is_available,_ = self.check_booking_availability(resource_id=resouce.id, date_start=slot_start_dt_utc, date_end=slot_end_dt_utc)
        return is_available

    def _slot_availability_is_employee_working(self, start_dt, end_dt, intervals):
        """ Check if the slot is contained in the employee's work hours
        (defined by intervals).

        TDE NOTE: internal method ``is_work_available`` of ``_slots_available``
        made as explicit method in 15.0 but left untouched. To clean in 15.3+.

        :param datetime start_dt: beginning of slot boundary. Not timezoned UTC;
        :param datetime end_dt: end of slot boundary. Not timezoned UTC;
        :param intervals: list of tuples defining working hours boundaries. If no
          intervals are given we consider employee does not work during this slot.
          See ``Resource._work_intervals_batch`` for more details;

        :return bool: whether employee is available for this slot;
        """
        def find_start_index():
            """ find the highest index of intervals for which the start_date
            (element [0]) is before (or at) start_dt """
            def recursive_find_index(lower_bound, upper_bound):
                if upper_bound - lower_bound <= 1:
                    if intervals[upper_bound][0] <= start_dt:
                        return upper_bound
                    return lower_bound
                index = (upper_bound + lower_bound) // 2
                if intervals[index][0] <= start_dt:
                    return recursive_find_index(index, upper_bound)
                return recursive_find_index(lower_bound, index)

            if start_dt <= intervals[0][0] - tolerance:
                return -1
            if end_dt >= intervals[-1][1] + tolerance:
                return -1
            return recursive_find_index(0, len(intervals) - 1)

        if not intervals:
            return False

        tolerance = timedelta(minutes=1)
        start_index = find_start_index()
        if start_index != -1:
            for index in range(start_index, len(intervals)):
                if intervals[index][1] >= end_dt - tolerance:
                    return True
                if len(intervals) == index + 1 or intervals[index + 1][0] - intervals[index][1] > tolerance:
                    return False
        return False

    def _slot_availability_prepare_values(self, staff_employees, start_dt, end_dt):
        """ Hook method used to prepare useful values in the computation of slots
        availability. Purpose is to prepare values (event meeting, work schedule)
        in batch instead of doing it in a loop in ``_slots_available``.

        Can be overridden to add custom values preparation to be used in custom
        overrides of ``_slot_availability_is_employee_available()``.

        :param <hr.employee> staff_employees: prepare values to check availability
          of those employees against given appointment boundaries. At this point
          timezone should be correctly set in context of those employees;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'partner_to_events': meetings (not declined), based on user_partner_id
              (see ``_slot_availability_prepare_values_meetings()``);
            'work_schedules': dict giving working hours based on user_partner_id
              (see ``_slot_availability_prepare_values_workhours()``);
          }
        }
        """
        result = self._slot_availability_prepare_values_workhours(staff_employees, start_dt, end_dt)
        result.update(self._slot_availability_prepare_values_meetings(staff_employees, start_dt, end_dt))
        return result

    def _slot_availability_prepare_values_meetings(self, resources, start_dt, end_dt):
        """ This method computes meetings of employees between start_dt and end_dt
        of appointment check.

        :param <hr.employee> staff_employees: prepare values to check availability
          of those employees against given appointment boundaries. At this point
          timezone should be correctly set in context of those employees;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;

        :return: dict containing main values for computation, formatted like
          {
            'partner_to_events': meetings (not declined), formatted as a dict
              {
                'user_partner_id': dict of day-based meetings: {
                  'date in UTC': calendar events;
                  'date in UTC': calendar events;
                  ...
              },
              { ... }
          }
        """
        all_events = self.env['calendar.event']
        partner_to_events = {}

        if self.resource_type == 'place':
            related_places = resources
            all_events = self.env['calendar.event'].search(
                ['&',
                 ('place_id', 'in', [p.id for p in related_places]),
                 '&',
                 ('stop', '>', datetime.combine(start_dt, time.min)),
                 ('start', '<', datetime.combine(end_dt, time.max)),
                 ],
                order='start asc',
            )
            for event in all_events:
                for place in event.place_id:
                    if place not in related_places:
                        continue

                    for day_dt in rrule(freq=DAILY,
                                              dtstart=event.start,
                                              until=event.stop,
                                              interval=1):
                        date_date = day_dt.date()  # map per day, not per hour
                        place_events = partner_to_events.setdefault(place, {})
                        if place_events.get(date_date):
                            place_events[date_date] += event
                        else:
                            place_events[date_date] = event

            return {'place_reservations': partner_to_events}

        # if resource is person
        related_partners = resources.user_partner_id

        # perform a search based on start / end being set to day min / day max
        # in order to include day-long events without having to include conditions
        # on start_date and allday

        if related_partners:
            all_events = self.env['calendar.event'].search(
                ['&',
                 ('partner_ids', 'in', related_partners.ids),
                 '&',
                 ('stop', '>', datetime.combine(start_dt, time.min)),
                 ('start', '<', datetime.combine(end_dt, time.max)),
                ],
                order='start asc',
            )

        for event in all_events:
            for attendee in event.attendee_ids:
                if attendee.state == 'declined' or attendee.partner_id not in related_partners:
                    continue
                for day_dt in rrule(freq=DAILY,
                                          dtstart=event.start,
                                          until=event.stop,
                                          interval=1):
                    partner_events = partner_to_events.setdefault(attendee.partner_id, {})
                    date_date = day_dt.date()  # map per day, not per hour
                    if partner_events.get(date_date):
                        partner_events[date_date] += event
                    else:
                        partner_events[date_date] = event

        return {'partner_to_events': partner_to_events}

    def _slot_availability_prepare_values_workhours(self, staff_employees, start_dt, end_dt):
        """ This method computes the work intervals of employees between start_dt
        and end_dt of slot. This means they have an employee using working hours.

        :param <hr.employee> staff_employees: prepare values to check availability
          of those employees against given appointment boundaries. At this point
          timezone should be correctly set in context of those employees;
        :param datetime start_dt: beginning of appointment check boundary. Timezoned to UTC;
        :param datetime end_dt: end of appointment check boundary. Timezoned to UTC;

        :return: dict with unique key 'work_schedules' (to ease master compatibility)
          being a dict of working intervals based on employee partners:
          {
            'user_partner_id.id': [tuple(work interval), tuple(work_interval), ...],
            'user_partner_id.id': work_intervals,
            ...
          }
          Calendar field is required on resource and therefore on employee so each
          employee should be correctly taken into account;
        """
        if self.category == 'custom':
            return {'work_schedules': {}}

        calendar_to_employees = {}
        # compute work schedules for employees having a resource.calendar
        for staff_employee in staff_employees:
            calendar = staff_employee.resource_id.calendar_id
            if not calendar:
                continue
            if calendar not in calendar_to_employees:
                calendar_to_employees[calendar] = staff_employee
            else:
                calendar_to_employees[calendar] += staff_employee

        # Compute work schedules for users having employees
        work_schedules = {}
        for calendar, employees in calendar_to_employees.items():
            work_intervals = calendar.sudo()._work_intervals_batch(
                start_dt, end_dt,
                resources=employees.resource_id
            )
            work_schedules.update(dict(
                (employee.user_partner_id if self.resource_type == 'person' else employee.id,
                 [(interval[0].astimezone(pytz.UTC).replace(tzinfo=None),
                   interval[1].astimezone(pytz.UTC).replace(tzinfo=None)
                  )
                  for interval in work_intervals[employee.resource_id.id]
                 ]
                )
                for employee in employees
            ))

        return {'work_schedules': work_schedules}

    def _get_booking_slots(self, timezone, employee=None, reference_date=None):

        self.ensure_one()
        if not reference_date:
            reference_date = datetime.utcnow()

        appt_tz = pytz.timezone(self.appointment_tz)
        requested_tz = pytz.timezone(timezone)
        first_day = requested_tz.fromutc(reference_date + relativedelta(hours=self.min_schedule_hours))
        appointment_duration_days = self.max_schedule_days
        unique_slots = self.slot_ids.filtered(lambda slot: slot.slot_type == 'unique')

        if self.category == 'custom' and unique_slots:
            appointment_duration_days = (unique_slots[-1].end_datetime - reference_date).days
        last_day = requested_tz.fromutc(reference_date + relativedelta(days=appointment_duration_days))

        # Compute available slots (ordered)
        slots = self._slots_generate(
            first_day.astimezone(appt_tz),
            last_day.astimezone(appt_tz),
            timezone,
            reference_date=reference_date
        )


        if self.resource_type == 'person':
            if not employee or employee in self.employee_ids:
                self._slots_available(slots, first_day.astimezone(pytz.UTC), last_day.astimezone(pytz.UTC), employee)
        else:
            if not employee or employee in self.places_ids:
                self._slots_available(slots, first_day.astimezone(pytz.UTC), last_day.astimezone(pytz.UTC),
                                          employee)


        # Compute calendar rendering and inject available slots
        today = requested_tz.fromutc(reference_date)
        start = today
        month_dates_calendar = cal.Calendar(0).monthdatescalendar
        months = []
        while (start.year, start.month) <= (last_day.year, last_day.month):
            dates = month_dates_calendar(start.year, start.month)
            for week_index, week in enumerate(dates):
                for day_index, day in enumerate(week):
                    mute_cls = weekend_cls = today_cls = None
                    today_slots = []
                    if day.weekday() in (cal.SUNDAY, cal.SATURDAY):
                        weekend_cls = 'o_weekend'
                    if day == today.date() and day.month == today.month:
                        today_cls = 'o_today'
                    if day.month != start.month:
                        mute_cls = 'text-muted o_mute_day'
                    else:
                        # slots are ordered, so check all unprocessed slots from until > day
                        while slots and (slots[0][timezone][0].date() <= day):
                            if (slots[0][timezone][0].date() == day) and ('employee_id' in slots[0]):
                                if slots[0]['slot'].allday:
                                    today_slots.append({
                                        'employee_id': slots[0]['employee_id'].id,
                                        'datetime': slots[0][timezone][0].strftime('%Y-%m-%d %H:%M:%S'),
                                        'hours': _("All day"),
                                        'duration': 24,
                                    })
                                else:
                                    start_hour = slots[0][timezone][0].strftime('%H:%M')
                                    end_hour = slots[0][timezone][1].strftime('%H:%M')
                                    today_slots.append({
                                        'employee_id': slots[0]['employee_id'].id,
                                        'datetime': slots[0][timezone][0].strftime('%Y-%m-%d %H:%M:%S'),
                                        'hours': "%s - %s" % (start_hour, end_hour) if self.category == 'custom' else start_hour,
                                        'duration': str((slots[0][timezone][1] - slots[0][timezone][0]).total_seconds() / 3600),
                                    })
                            slots.pop(0)
                    today_slots = sorted(today_slots, key=lambda d: d['hours'])
                    dates[week_index][day_index] = {
                        'day': day,
                        'slots': today_slots,
                        'mute_cls': mute_cls,
                        'weekend_cls': weekend_cls,
                        'today_cls': today_cls
                    }

            months.append({
                'id': len(months),
                'month': format_datetime(start, 'MMMM Y', locale=get_lang(self.env).code),
                'weeks': dates,
            })
            start = start + relativedelta(months=1)
        return months

    #-------------------------------------------------
    # Multi Recurring
    #-------------------------------------------------

    def get_available_days(self, *args, **kwargs):
        timezone = args[0][0]
        employee_id = args[0][1]

        booking_profile_id = args[0][2]
        booking_profile = self.env['tanmia.booking.book.profile'].browse(int(booking_profile_id))
        employee = self.env['hr.employee'].browse(int(employee_id)) if booking_profile.resource_type == 'person' else self.env['account.asset'].sudo().browse(int(employee_id))
        slots = booking_profile._get_booking_slots(timezone, employee, None)
        available_days = []
        for month in slots:
            for week in month['weeks']:
                for day in week:
                    if len(day['slots']) > 0:
                        available_days.append(day['day'].strftime("%A"))
        return list(set(available_days))

    def get_available_hours(self, *args, **kwargs):
        timezone = args[0][0]
        employee_id = args[0][1]
        booking_profile_id = args[0][2]
        _day = args[0][3]
        booking_profile = self.env['tanmia.booking.book.profile'].browse(int(booking_profile_id))
        employee = self.env['hr.employee'].browse(int(employee_id)) if booking_profile.resource_type == 'person' else self.env['account.asset'].sudo().browse(int(employee_id))
        slots = booking_profile._get_booking_slots(timezone, employee, None)
        available_hours = []
        for month in slots:
            for week in month['weeks']:
                for day in week:
                    if len(day['slots']) > 0:
                        if _day == day['day'].strftime("%A"):
                            available_hours.append(day['slots'])
        return max(available_hours, key=len)

    def get_max_recurrence_repeat(self, *args):
        repeat_unit = REPEAT_UNIT.get(args[0][0])
        repeat_day = DAYS.get(args[0][1])
        repeat_week = WEEKS.get(args[0][2]) if args[0][2] != -1 else False
        repeat_day = repeat_day(repeat_week) if repeat_week != False else repeat_day
        repeat_interval = int(args[0][3])
        booking_profile_id = args[0][4]
        booking_profile = self.env['tanmia.booking.book.profile'].browse(int(booking_profile_id))
        max_schedule_days = booking_profile.max_schedule_days
        tomorrow = date.today() + relativedelta(days=1)
        upper_bound_date = (date.today() + relativedelta(days=max_schedule_days))
        date_start = tomorrow
        dates_str = []
        while True:
            res = rrule(freq=repeat_unit, interval=repeat_interval, count=1, byweekday=repeat_day, dtstart=date_start)
            date_start = res[0].date() + relativedelta(days=1)
            if res[0].date() > upper_bound_date:
                break
            else:
                dates_str.append(res[0].date().strftime('%Y/%m/%d'))
        return (dates_str, len(dates_str))

    def get_recurring_dates(self, *args):
        repeat_unit = REPEAT_UNIT.get(args[0][0])
        repeat_day = DAYS.get(args[0][1])
        repeat_week = WEEKS.get(args[0][2]) if args[0][2] != -1 else False
        repeat_day = repeat_day(repeat_week) if repeat_week != False else repeat_day
        repeat_interval = int(args[0][3])
        repeat_until = args[0][4]
        repeat_hour = args[0][5]
        booking_profile_id = args[0][6]
        employee_id = args[0][7]
        booking_profile = self.env['tanmia.booking.book.profile'].browse(int(booking_profile_id))
        tomorrow = date.today() + relativedelta(days=1)
        date_start = tomorrow
        dates = []
        if isinstance(repeat_until, int):
            res = rrule(freq=repeat_unit, interval=repeat_interval, count=repeat_until, byweekday=repeat_day, dtstart=date_start)
            dates = [dt.date() for dt in res]
        else:
            upper_bound_date = datetime.strptime(repeat_until, '%Y-%m-%d').date()
            while True:
                res = rrule(freq=repeat_unit, interval=repeat_interval, count=1, byweekday=repeat_day, dtstart=date_start)
                date_start = res[0].date() + relativedelta(days=1)
                if res[0].date() > upper_bound_date:
                    break
                else:
                    dates.append(res[0].date())
        appointments = [
            {
             "employee_id": "{}".format(employee_id),
             "datetime": "{} {}:00".format(_date.strftime('%Y-%m-%d'), repeat_hour),
             "hours": "{}".format(repeat_hour),
             "duration": "{}".format(booking_profile.appointment_duration)
            } for _date in dates
        ]
        return appointments

    def get_max_schedule_days(self, *args):
        booking_profile_id = args[0][0]
        booking_profile = self.env['tanmia.booking.book.profile'].browse(int(booking_profile_id))
        return booking_profile.max_schedule_days