# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.addons.http_routing.models.ir_http import slug


class BookProfile(models.Model):
    _name = "tanmia.booking.book.profile"
    _inherit = [
        'tanmia.booking.book.profile',
        'website.seo.metadata',
        'website.published.mixin',
        'website.cover_properties.mixin',
    ]

    @api.model
    def default_get(self, default_fields):
        result = super().default_get(default_fields)
        if result.get('category') in ['custom', 'work_hours']:
            result['is_published'] = True
        return result

    def _default_cover_properties(self):
        res = super()._default_cover_properties()
        res.update({
            'background-image': 'url("/website_resouce_booking/static/src/img/appointment_cover_0.jpg")',
            'resize_class': 'o_record_has_cover o_half_screen_height',
            'opacity': '0.4',
        })
        return res

    is_published = fields.Boolean(
        compute='_compute_is_published', default=None,  # force None to avoid default computation from mixin
        readonly=False, store=True)

    @api.depends('category')
    def _compute_is_published(self):
        for book in self:
            if book.category in ['custom', 'work_hours']:
                book.is_published = True
            else:
                book.is_published = False

    def _compute_website_url(self):
        super(BookProfile, self)._compute_website_url()
        for book in self:
            if book.id:
                book.website_url = '/booking/%s/profile' % (slug(book),)
            else:
                book.website_url = False

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """ Force False manually for all categories of appointment type when duplicating
        even for categories that should be auto-publish. """
        default = default if default is not None else {}
        default['is_published'] = False
        return super().copy(default)

    def get_backend_menu_id(self):
        return self.env.ref('calendar.mail_menu_calendar').id
