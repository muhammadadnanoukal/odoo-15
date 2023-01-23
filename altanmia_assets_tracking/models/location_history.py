from odoo import api, fields, models, _, tools


class LocationHistory(models.Model):
    _name = "tanmia.assets.location.history"
    _order = 'start desc'

    location = fields.Many2one('stock.location', string='Location', change_default=True, index=True, tracking=True)
    asset_id = fields.Many2one('account.asset', string='Asset', tracking=True)
    start = fields.Datetime(string='From', required=True, default=lambda self: fields.Datetime.now())
    end = fields.Datetime(string='to')
    notice = fields.Html(string="Notice", translate=True, tracking=True)

    @api.model
    def create(self, vals):
        for current in self.search([('end', '=', False)]):
            current.write({'end': fields.Datetime.now()})
        return super(LocationHistory, self).create(vals)
