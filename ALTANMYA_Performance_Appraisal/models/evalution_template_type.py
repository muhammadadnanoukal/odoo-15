from odoo import models, fields, api, _


class EvaluationTemplateType(models.Model):
    _name = 'evaluation.template.type'
    _description = 'Evaluation Template Type'

    name = fields.Char(string='Name', readonly=True, required=True, default=lambda self: _('New'))
    scoring_system = fields.Many2one('evaluation.scoring.system', required=True, store=True)
    section_ids = fields.One2many('evaluation.template.type.section', 'evaluation_template_type_id', store=True)
    evaluation_type = fields.Selection([
        ('production', "Production"),
        ('administrators', "Administrators"),
        ('technician_process_administrators', "Technician Process Administrators"),
        ('employment', "Employment"),
        ('sales_and_marketing', "Sales & Marketing"),
        ('technician', "Technician"),
    ], default=False, help="Technical field for UX purpose.")

    score_note_selection = fields.Selection([
        ('document', "Document"),
        ('note', "Note"),
        ('both', 'Both'),
        ('note_or_document', 'Note or Document')
    ], string='Choose Between Note, Document or Both', default='note', help="Technical field for UX purpose.")

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.template.type')
            vals['name'] = seq_name or _('New')
        result = super(EvaluationTemplateType, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationTemplateType, self).copy(default=default)

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'section_ids' not in default:
            default['section_ids'] = [(0, 0, line.copy_data()[0]) for line in self.section_ids]
        return super(EvaluationTemplateType, self).copy_data(default)
