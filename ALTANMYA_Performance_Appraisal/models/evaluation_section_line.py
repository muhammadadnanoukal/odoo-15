from odoo import models, fields, api, _
from odoo.http import request

class EvaluationSectionLine(models.Model):
    _name = 'evaluation.section.line'
    _description = 'Evaluation Section Line'

    name = fields.Char(string="Name", required=True)
    criterion_id = fields.Many2one('evaluation.criterion', store=True, string="Criterion", required=True, readonly=True)

    @api.onchange('criterion_id')
    def _onchange_criterion_id(self):
        return {'domain': {'score': [('id', 'in', self.section_id.evaluation_template_id.scoring_system.score_pair_ids.ids)]}}

    score = fields.Many2one('evaluation.score.pair', string="Score")
    weight = fields.Float(string="Weight", related='criterion_id.weight')
    final_score = fields.Float(string="Item Score", compute="_compute_final_score", required=True)
    notes = fields.Html(string="Notes", required=False)
    section_id = fields.Many2one('evaluation.section', store=True)
    section_type = fields.Selection(related='section_id.section_type_id.type')

    is_user_creator = fields.Boolean(compute='_compute_is_user_creator', default=False)

    @api.depends('section_id')
    def _compute_is_user_creator(self):
        for rec in self:
            if self.env.user.has_group('ALTANMYA_Performance_Appraisal.evaluation_group_creators'):
                rec.is_user_creator = True
            else:
                rec.is_user_creator = False

    @api.depends('score', 'weight')
    def _compute_final_score(self):
        for rec in self:
            rec.final_score = rec.score.score * rec.weight

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.section.line')
            vals['name'] = seq_name or _('New')
        result = super(EvaluationSectionLine, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationSectionLine, self).copy(default=default)

