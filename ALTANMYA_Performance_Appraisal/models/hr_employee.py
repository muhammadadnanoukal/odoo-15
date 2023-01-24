from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    hr_responsible = fields.Many2one('res.users', string="HR Responsible")
    evaluation_template_type_id = fields.Many2one('evaluation.template.type', string="Evaluation Template Type")
    has_evaluation = fields.Boolean(string="Has Evaluation")
