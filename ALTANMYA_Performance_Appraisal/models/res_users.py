from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'res.users'

    evaluation_template_id = fields.Many2one('evaluation.template', string='Evaluation Template')

