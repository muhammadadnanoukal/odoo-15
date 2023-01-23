# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name' : 'Assets Tracking',
    'version' : '1.0.0',
    'summary': 'Assets Management and Tracking',
    'sequence': -50,
    'description': """
            Assets Tracking
            ====================
            Description
                """,
    'category': 'Accounting/Accounting',
    'website': 'https://www.odoo.com/app/invoicing',
    'images' : [],
    'depends' : ['mail','account_asset','calendar','maintenance','stock','fleet'],
    'data': [
        'views/reserve_view.xml',
        'views/assets_view.xml',
        'views/assets_tag_view.xml',
        'views/material_view.xml',
        'views/main_menu.xml',
        'data/sequence_data.xml',
        'security/ir.model.access.csv',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {},
    'license': 'LGPL-3',
}
