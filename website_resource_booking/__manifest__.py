# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Website Booking Resource',
    'version': '1.0',
    'category': 'Marketing/Resources Booking',
    'sequence': 200,
    'website': 'https://www.odoo.com/app/booking',
    'description': """
Allow clients to Schedule Appointments or booking through your Website
-------------------------------------------------------------

""",
    'depends': ['website','altanmia_resource_booking', 'sale', 'website_payment', 'website_mail', 'portal_rating', 'digest'],
    'data': [
        'data/website_data.xml',
        'views/website_enterprise_templates.xml',
        'views/calendar_booking_profile_views.xml',
        'views/calendar_menus.xml',
        'views/calendar_templates.xml',
        'views/website_templates.xml',
        'security/website_booking.xml',
        'security/calendar_security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
    'post_init_hook': '_post_init_website_resource_booking',
    'license': 'OEEL-1',
    'assets': {
        'website.assets_editor': [
            'website_resource_booking/static/src/js/website_appointment.editor.js',
        ],
        'web.assets_tests': [
            'website_resource_booking/static/tests/tours/*',
        ],
        'web.assets_frontend': [
            'website_enterprise/static/src/**/*',
        ],
    }
}
