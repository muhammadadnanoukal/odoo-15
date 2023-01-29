# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'HyperPay Payment Acquirer',
    'version': '2.0',
    'category': 'Accounting/Payment Acquirers',
    'sequence': 365,
    'summary': 'Payment Acquirer: HyperPay Implementation',
    'description': """HyperPay Payment Acquirer""",
    'depends': ['payment'],
    'data': [
        'views/payment_views.xml',
        'views/payment_hyperpay_templates.xml',
        'data/payment_acquirer_data.xml',
        'data/payment_hyperpay_email_data.xml',
    ],
    'application': True,
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web.assets_frontend': [ ],
    },
    'license': 'LGPL-3',
}
