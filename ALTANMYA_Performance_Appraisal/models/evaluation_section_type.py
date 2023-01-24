from odoo import models, fields, api, _


class EvaluationSectionType(models.Model):
    _name = 'evaluation.section.type'
    _description = 'Evaluation Section Type'

    name = fields.Char(string='Name', default=lambda x: _('New'))
    type = fields.Selection(selection=[
        ('objectives', "Objectives"),
        ('kpis', "KPIs"),
        ('behavioral_competencies', "Behavioral Competencies"),
        ('hr_department', "HR Department"),
    ])
    percentage = fields.Float(string='Weight')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.section.type')
            s_type = self.get_type(vals['type'])
            vals['name'] = s_type + ' - ' + seq_name or _('New')
        result = super(EvaluationSectionType, self).create(vals)
        return result

    def get_type(self, type):
        if type == 'objectives':
            return "Objectives"
        if type == 'kpis':
            return "KPIs"
        if type == 'behavioral_competencies':
            return "Behavioral Competencies"
        if type == 'hr_department':
            return "HR Department"

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationSectionType, self).copy(default=default)


