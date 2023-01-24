from odoo import models, fields, api, _


class EvaluationScoringSystem(models.Model):
    _name = 'evaluation.scoring.system'
    _description = 'Evaluation Scoring System'

    name = fields.Char(required=True, default=lambda x: _('New'))
    scoring_system_name = fields.Char(string='Scoring System Name')
    score_pair_ids = fields.One2many('evaluation.score.pair', 'scoring_system_id', string='Score & Rate', store=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.scoring.system')
            vals['name'] = vals['scoring_system_name'] + ' - ' + seq_name or _('New')
        result = super(EvaluationScoringSystem, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationScoringSystem, self).copy(default=default)
