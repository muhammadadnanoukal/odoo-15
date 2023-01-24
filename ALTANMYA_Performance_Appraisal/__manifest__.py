# -*- coding: utf-8 -*-
###################################################################################
#
#    ALTANMYA - TECHNOLOGY SOLUTIONS
#    Copyright (C) 2022-TODAY ALTANMYA - TECHNOLOGY SOLUTIONS Part of ALTANMYA GROUP.
#    ALTANMYA - Discount Extension in Purchasing Module.
#    Author: ALTANMYA for Technology(<https://tech.altanmya.net>)
#
#    This program is Licensed software: you can not modify
#   #
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###################################################################################
{
    'name': "ALTANMYA Performance Appraisal",
    'summary': """An Evaluation Module for Employees Performance Review. 
        """,
    'description': """
        A Periodic Appraisal for Employees Performance by the HR Department and Their Managers.
    """,
    'author': 'ALTANMYA - TECHNOLOGY SOLUTIONS',
    'company': 'ALTANMYA - TECHNOLOGY SOLUTIONS Part of ALTANMYA GROUP',
    'website': "http://tech.altanmya.net",
    'category': 'Human Resources/Appraisals',
    'version': '1.0',
    'sequence': -3000,
    'depends': ['base', 'hr', 'hr_appraisal', 'portal', 'utm', 'mail', 'web'],
    'data': [
        'data/ir_sequence_data.xml',
        'data/evaluation_calendar_data.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/evaluation_template_views.xml',
        'views/evaluation_section_views.xml',
        'views/evaluation_section_line_views.xml',
        'views/evaluation_scoring_system_views.xml',
        'views/evaluation_section_type_views.xml',
        'views/evaluation_criterion_views.xml',
        'views/evaluation_template_type_views.xml',
        'views/evaluation_template_type_section_views.xml',
        'views/hr_employee_views.xml',
        'report/report_info.xml',
        'report/ev_report.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3'
}
