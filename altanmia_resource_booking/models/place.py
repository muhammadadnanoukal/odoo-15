from ast import literal_eval

from odoo import api, fields, models
from pytz import timezone, UTC, utc
from datetime import timedelta, datetime, time

from odoo.tools import format_time
import pytz


class Place(models.Model):
    _name = "tanmia.booking.place"
    _description = "Reservable Place"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'resource.mixin', 'avatar.mixin']

    name = fields.Char()
    active = fields.Boolean("Active", default=True)
    color = fields.Integer('Color Index', default=0)

    company_id = fields.Many2one('res.company',required=True)
    company_country_id = fields.Many2one('res.country', 'Company Country', related='company_id.country_id', readonly=True)
    company_country_code = fields.Char(related='company_country_id.code', readonly=True)

    resource_id = fields.Many2one('resource.resource')
    resource_calendar_id = fields.Many2one('resource.calendar', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    asset_id = fields.Many2one('account.asset')

    location = fields.Many2one(related='asset_id.location', string='Location')
    capacity = fields.Integer(related='asset_id.capacity')

    tz = fields.Selection(
        string='Timezone', related='resource_id.tz', readonly=False,
        help="This field is used in order to define in which timezone the resources will work.")

    def _get_tz(self):
        # Finds the first valid timezone in his tz, his work hours tz,
        #  the company calendar tz or UTC and returns it as a string
        self.ensure_one()
        return self.tz or\
               self.resource_calendar_id.tz or\
               self.company_id.resource_calendar_id.tz or\
               'UTC'

    def _get_tz_batch(self):
        # Finds the first valid timezone in his tz, his work hours tz,
        #  the company calendar tz or UTC
        # Returns a dict {employee_id: tz}
        return {place.id: place._get_tz() for place in self}

    def calendar_verify_availability(self, date_start, date_end):
        """ Verify availability of the partner(s) between 2 datetimes on their calendar.

        :param datetime date_start: beginning of slot boundary. Not timezoned UTC;
        :param datetime date_end: end of slot boundary. Not timezoned UTC;
        """
        all_events = self.env['calendar.event']
        if self:
            all_events = self.env['calendar.event'].search(
                ['&',
                 ('place_id', 'in', self.ids),
                 '&',
                 ('stop', '>', datetime.combine(date_start, time.min)),
                 ('start', '<', datetime.combine(date_end, time.max)),
                ],
                order='start asc',
            )
        reserved = 0

        for event in all_events:
            estart = pytz.utc.localize(event.start)
            eend = pytz.utc.localize(event.stop)
            if event.allday or (estart < date_end and eend > date_start):
                reserved +=1

        if reserved == self.capacity:
            return False
        return True
