from odoo import models, fields, api, _


class EvaluationScoreRate(models.Model):
    _name = 'evaluation.score.pair'
    _description = 'Evaluation Score-Rate'

    name = fields.Char(required=True, default=lambda x: _('New'))
    rate = fields.Char(string='Rate')
    score = fields.Integer(string='Score')
    scoring_system_id = fields.Many2one('evaluation.scoring.system', store=True)

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, '%s' % rec.rate))
        return result