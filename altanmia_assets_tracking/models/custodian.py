from odoo import api, fields, models, _, tools


class Custodian(models.Model):
    _name = "tanmia.assets.custodian"
    _order = 'start_responsibility desc'

    responsible_person = fields.Many2one('res.partner', string='Responsible Person',  required=True, tracking=True)
    asset_id = fields.Many2one('account.asset', string='Asset', tracking=True)
    start_responsibility = fields.Datetime(string='From', required=True, default=lambda self: fields.Datetime.now())
    end_responsibility = fields.Datetime(string='to')
    notice = fields.Html(string="Notice", translate=True, tracking=True)

    @api.model
    def create(self, vals):
        for current in self.search([('end_responsibility', '=', False)]):
            current.write({'end_responsibility': fields.Datetime.now()})
        return super(Custodian, self).create(vals)
