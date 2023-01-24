from odoo import models, fields, api, _


class EvaluationTemplateTypeSection(models.Model):
    _name = 'evaluation.template.type.section'
    _description = 'Evaluation Template Type Section'

    name = fields.Char(required=True, default=lambda x: _('New'))
    section_type_id = fields.Many2one('evaluation.section.type', string='Evaluation Section Type', required=True, store=True)
    weight = fields.Float(string="Weight", related='section_type_id.percentage')
    evaluation_template_type_id = fields.Many2one('evaluation.template.type', store=True)
    evaluation_responsibility = fields.Selection([
        ('manager', "Manager"),
        ('hr', "HR"),
        ('specific_user', "Specific User"),
    ], help="Technical field for UX purpose.", default='manager')
    specific_user = fields.Many2one('res.users', string="Specific User Responsible", store=True)
    section_line_ids = fields.One2many('evaluation.template.type.section.line', 'section_id', store=True)
    company_id = fields.Many2one('res.company', 'Company', required=True,
                                 default=lambda self: self.env.company, store=True)

    @api.onchange('evaluation_responsibility')
    def _onchange_evaluation_responsibility(self):
        if self.evaluation_responsibility != 'specific_user':
            self.specific_user = None

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.template.type.section')
            vals['name'] = seq_name or _('New')
        result = super(EvaluationTemplateTypeSection, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationTemplateTypeSection, self).copy(default=default)

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'section_line_ids' not in default:
            default['section_line_ids'] = [(0, 0, line.copy_data()[0]) for line in self.section_line_ids]
        return super(EvaluationTemplateTypeSection, self).copy_data(default)
