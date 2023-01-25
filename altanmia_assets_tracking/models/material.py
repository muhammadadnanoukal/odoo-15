from odoo import api, fields, models, _, tools

class Material(models.Model):
    _name = "tanmia.assets.material"
    _inherit = ["mail.thread", 'mail.activity.mixin']
    _description = "Add edit remove materials"

    name = fields.Char(string="Name", required=True, translate=True, tracking=True)
    description = fields.Char(string="Description", required=True, translate=True, tracking=True)
    active = fields.Boolean(string="active", default=True, tracking=True)
