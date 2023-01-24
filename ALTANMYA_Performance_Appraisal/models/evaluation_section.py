from odoo import models, fields, api, _


class EvaluationSection(models.Model):
    _name = 'evaluation.section'
    _description = 'Evaluation Section'

    user_id = fields.Integer('Current User', default=lambda self: self.env.user.id)
    name = fields.Char(required=True, default=lambda x: _('New'))
    section_type_id = fields.Many2one('evaluation.section.type', string='Evaluation Section Type', required=True, store=True)
    weight = fields.Float(string="Weight", related='section_type_id.percentage')
    final_score = fields.Float(string="Section Score", compute="_compute_final_score", required=True)
    notes = fields.Html(string="Notes", required=False)
    evaluation_template_id = fields.Many2one('evaluation.template', store=True)
    section_line_ids = fields.One2many('evaluation.section.line', 'section_id', store=True)
    section_responsible_user_id = fields.Many2one('res.users', store=True)

    is_user_creator = fields.Boolean(compute='_compute_is_user_creator', default=False)

    def _compute_is_user_creator(self):
        for rec in self:
            if self.env.user.has_group('ALTANMYA_Performance_Appraisal.evaluation_group_creators'):
                rec.is_user_creator = True
            else:
                rec.is_user_creator = False

    def read(self, fields=None, load='_classic_read'):
        res = super(EvaluationSection, self).read(fields=fields, load=load)
        return res

    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], required=True, string='Status', readonly=True, copy=False, store=True, default='in_progress')

    def button_done(self):
        self.state = 'done'

    def button_draft(self):
        self.state = 'in_progress'

    @api.depends('weight', 'section_line_ids')
    def _compute_final_score(self):
        for rec in self:
            for line in rec.section_line_ids:
                rec.final_score += line.final_score

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.section')
            vals['name'] = seq_name or _('New')
        result = super(EvaluationSection, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationSection, self).copy(default=default)

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'section_line_ids' not in default:
            default['section_line_ids'] = [(0, 0, line.copy_data()[0]) for line in self.section_line_ids]
        return super(EvaluationSection, self).copy_data(default)

