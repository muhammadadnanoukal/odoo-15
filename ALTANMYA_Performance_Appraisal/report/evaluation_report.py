from odoo import models, api


class EvaluationReport(models.AbstractModel):
    _name = 'report.altanmya_performance_appraisal.et_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        report = self.env['ir.actions.report']._get_report_from_name('altanmya_performance_appraisal.et_report')
        obj = self.env[report.model].browse(docids)
        return {
            'yo': 'HERE',
            'lines': docids.get_lines()
        }