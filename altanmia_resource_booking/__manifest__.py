# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Resources Booking',
    'version': '1.0',
    'category': 'Marketing/Resources Booking',
    'sequence': -60,
    'summary': 'Allow people to book meetings or room in place in your agenda',
    'website': 'https://www.odoo.com/app/booking',
    'description': """
        Allow clients to Schedule Appointments or booking through the Portal
    """,
    'depends': ['sale','website_sale', 'sales_team', 'payment', 'utm','product','account_asset', 'website_payment', 'calendar_sms', 'hr', 'portal'],
    'data': [
        'data/mail_data.xml',
        'data/mail_template_data.xml',
        'views/calendar_event_views.xml',
        'views/payment_template.xml',
        'views/question_views.xml',
        'views/book_profile_views.xml',
        'views/slot_views.xml',
        'views/main_menu.xml',
        'views/res_config_settings_views.xml',
        'views/calendar_templates.xml',
        'views/portal_templates.xml',
        'wizard/calendar_appointment_share_views.xml',
        'security/calendar_security.xml',
        'security/booking_security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OEEL-1',
    'assets': {
        'web_editor.assets_wysiwyg': [
            'altanmia_resource_booking/static/src/js/wysiwyg.js',
        ],
        'web.assets_frontend': [
            'altanmia_resource_booking/static/src/scss/appointment.scss',
            'altanmia_resource_booking/static/src/js/select_booking_profile.js',
            'altanmia_resource_booking/static/src/js/select_booking_slot.js',
            'altanmia_resource_booking/static/src/css/style.scss',
            'altanmia_resource_booking/static/src/js/script.js',
        ],
        'web.assets_backend': [
            'altanmia_resource_booking/static/src/scss/calendar_appointment_type_views.scss',
            'altanmia_resource_booking/static/src/scss/web_calendar.scss',
            'altanmia_resource_booking/static/src/js/calendar_controller.js',
            'altanmia_resource_booking/static/src/js/calendar_model.js',
            'altanmia_resource_booking/static/src/js/calendar_renderer.js',
        ],
        'web.assets_qweb': [
            'altanmia_resource_booking/static/src/xml/**/*',
        ],
        'web.qunit_suite_tests': [
            'altanmia_resource_booking/static/tests/*',
        ],
    }
}
