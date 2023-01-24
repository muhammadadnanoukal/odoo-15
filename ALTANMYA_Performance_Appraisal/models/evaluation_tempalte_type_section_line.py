from odoo import models, fields, api, _


class EvaluationTemplateTypeSectionLine(models.Model):
    _name = 'evaluation.template.type.section.line'
    _description = 'Evaluation Template Type Section Line'

    name = fields.Char(string="Name", required=True)
    criterion_id = fields.Many2one('evaluation.criterion', string="Criterion", required=True,
                                   domain="[('type', '=', section_type)]", store=True)
    weight = fields.Float(string="Weight", related='criterion_id.weight')
    section_id = fields.Many2one('evaluation.template.type.section', store=True)
    section_type = fields.Selection(related='section_id.section_type_id.type')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.template.type.section.line')
            vals['name'] = seq_name or _('New')
        result = super(EvaluationTemplateTypeSectionLine, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationTemplateTypeSectionLine, self).copy(default=default)


