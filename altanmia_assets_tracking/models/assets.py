from odoo import api, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError


class Assets(models.Model):
    _inherit = ['account.asset']
    capacity = fields.Integer(string="Capacity", tracking=True, default=1)

    location = fields.Many2one('stock.location', string='Location',compute="get_current_location", change_default=True, index=True, tracking=True)

    ref = fields.Char(string="Reference")
    notice = fields.Html(string="Notice", translate=True, tracking=True)
    sequence = fields.Integer('Sequence', default=20)
    category = fields.Selection(
        [('product', 'Product'), ('car', 'Vehicle'), ('material', 'Material'), ('person', 'Person'),
         ('equipment', 'Equipment')]
        , string="Category", tracking=True)
    #category = fields.Selection(lambda self: self._get_category_selection(), string="Category", tracking=True)
    product_id = fields.Many2one('product.product', string='Product', tracking=True,  domain=[('tracking', '=', 'serial')])
    product_lots_serial = fields.Many2one('stock.production.lot', string='Lots/Serial Numbers', tracking=True)
    vehicle_model = fields.Many2one('fleet.vehicle.model', string='Vehicle', tracking=True, readonly=False)
    person_id = fields.Many2one('res.partner', string='Person', tracking=True)
    material_id = fields.Many2one('tanmia.assets.material', string='Material', tracking=True)
    equipment_id = fields.Many2one('maintenance.equipment', string='Equipment', tracking=True)

    depended = fields.Selection(
        [('product', 'Product'), ('car', 'Vehicle'), ('material', 'Material'), ('person', 'Person'),
         ('equipment', 'Equipment')],
        string="Dependent type", tracking=True)
    depended_product_id = fields.Many2one('product.product', string='Depended on Product', tracking=True)
    depended_vehicle_id = fields.Many2one('fleet.vehicle.model', string='Depended on Vehicle', tracking=True)
    depended_person_id = fields.Many2one('res.partner', string='Depended on Person', tracking=True)
    depended_material_id = fields.Many2one('tanmia.assets.material', string='Depended on Material', tracking=True)
    depended_equipment_id = fields.Many2one('maintenance.equipment', string='Depended on Equipment', tracking=True)

    alternative_product_id = fields.Many2one('product.product', string='Alternative Product', tracking=True)
    alternative_vehicle_id = fields.Many2one('fleet.vehicle.model', string='Alternative Vehicle', tracking=True)
    alternative_person_id = fields.Many2one('res.partner', string='Alternative Person', tracking=True)
    alternative_material_id = fields.Many2one('tanmia.assets.material', string='Alternative Material', tracking=True)
    alternative_equipment_id = fields.Many2one('maintenance.equipment', string='Alternative Equipment', tracking=True)

    parent = fields.Many2one('account.asset', string='Parent', tracking=True)
    parts = fields.One2many("account.asset", 'parent', string="Parts", tracking=True)

    tags = fields.Many2many('tanmia.assets.assets_tag', string='Tags', tracking=True)
    # custodian = fields.Many2one('res.partner', string='Custodian', tracking=True)
    custodians = fields.One2many('tanmia.assets.custodian', 'asset_id', string='Custodians Log', tracking=True)
    current_custodian = fields.Char(compute="get_current_custodian", string='Custodian')
    reservations = fields.One2many("tanmia.assets.reservation", 'asset', string="Reservations")
    # dispose_with_parts = fields.Selection([('with_parts', 'Disposal of the asset and its parts'), ('check_parts', 'Prevent disposing, if one part is Running')],
    #                             string="Disposing Method", tracking=True, default="with_parts")

    depreciation_level = fields.Selection([('asset_level', 'Depreciation at asset level'), ('parts_level', 'Depreciation at parts level'),
                    ('parent_level', 'Depreciation at parent level')],
        string="Depreciation Level", tracking=True, default="asset_level")

    state = fields.Selection(selection_add=[('inuse', 'In Use')])

    depreciation_parts_move_ids = fields.One2many('account.move',compute='get_parts_depreciation_move', string='Parts')


    def _get_category_selection(self):
        selection =[]
        selection.append(('material', 'Material'))
        selection.append(('person', 'Person'))

        if self.env['ir.module.module'].search([('name', '=', 'stock'),('state','=','installed')]):
            selection.append(('product', 'Product'))

        if self.env['ir.module.module'].search([('name', '=', 'maintenance'),('state','=','installed')]):
            selection.append(('equipment', 'Equipment'))

        if self.env['ir.module.module'].search([('name', '=', 'fleet'),('state','=','installed')]):
            selection.append(('car', 'Vehicle'))

        return selection

    def get_parts_depreciation_move(self):
        self.depreciation_parts_move_ids = self.get_on_parts_dep()

    def get_on_parts_dep(self):
        for record in self:
            if record.parts:
                result = None
                for part in record.parts:
                    if not result:
                        result = part.get_on_parts_dep()
                    else:
                        result += part.get_on_parts_dep()
                return result
            else:
                return record.depreciation_move_ids

    @api.onchange('parent')
    def onchange_parent(self):
        if self.parent and self.parent.depreciation_level == 'asset_level':
            self.depreciation_level = 'parent_level'
        else:
            self.depreciation_level = 'asset_level'

    @api.constrains('depreciation_level')
    def validation_depreciation_level(self):
        for record in self:
            if record.parent and record.parent.depreciation_level == 'asset_level' and record.depreciation_level != 'parent_level':
                raise ValidationError(_("Parent depreciation at asset level, the parts depreciation should be at parent level"))
            if record.parent and record.parent.depreciation_level == 'parts_level' and record.depreciation_level == 'parent_level':
                raise ValidationError(_("Parent depreciation at parts level, the parts depreciation should be at asset level or at "
                            "parts level"))
            if record.parent and record.parent.depreciation_level == 'parent_level' and record.depreciation_level != 'parent_level':
                raise ValidationError(_("Parent depreciation at parent level, the parts depreciation should be at parent level"))
            if not record.parent and record.depreciation_level == 'parent_level':
                raise ValidationError(_("Asset has no parent, you can't set depreciation at parent level"))

    @api.model
    def create(self, vals):
        vals['ref'] = self.env['ir.sequence'].next_by_code('asset.no')
        return super(Assets, self).create(vals)

    def open_asset_reservations(self):
        """ This opens the xml view specified in xml_id for the current vehicle """
        self.ensure_one()
        res = self.env['ir.actions.act_window']._for_xml_id('altanmia_assets_tracking.action_reserves_show')
        res.update(
            context=dict(self.env.context, asset=self.id, default_asset=self.id, group_by=False),
            domain=[('asset', '=', self.id)]
        )
        return res

    def set_to_close(self, invoice_line_id, date=None):

        # if depreciation at parts level check children
        if self.depreciation_level == 'parts_level':
            # if one of children open, prevent closing parent
            if self.parts.filtered(lambda a: a.state in ('draft', 'open', 'inuse')):
                raise UserError(
                    _("You Cannot Dispose asset has running part.\n Please use 'Dispose' on the parts first."))
            else:
                self.write({'state': 'close'})
        # if depreciation at asset level check brothers
        elif self.depreciation_level == 'asset_level':
            # close all cheldren before closing
            for part in self.parts:
                part.set_to_close()
            super(Assets, self).set_to_close(invoice_line_id, date)
            # if all brothers close, close parent
            if self.parent != False and not self.parent.parts.filtered(
                    lambda a: a.state in ('draft', 'open')):
                self.parent.set_to_close(invoice_line_id, date)

        # if depreciation at parent level
        elif self.depreciation_level == 'parent_level':
            # close all cheldren before closing
            for part in self.parts:
                part.set_to_close()
            self.write({'state': 'close'})

    def validate(self):
        # if asset in running or in use state
        if self.state in ('inuse', 'open'):
            return
        result = None
        #run the asset
        if self.depreciation_level == 'asset_level':
            result =  super(Assets, self).validate()
        elif self.depreciation_level in ('parts_level', 'parent_level') :
            self.write({'state': 'inuse'})

        # run parent
        if self.parent:
            self.parent.validate()

        # run parts
        for part in self.parts:
            part.validate()

        return result

    def compute_depreciation_board(self):

        if self.depreciation_level == 'asset_level':
            return super(Assets, self).compute_depreciation_board()
        elif self.depreciation_level == 'parts_level':
            success = True
            for part in self.parts:
                success &= part.compute_depreciation_board()
            return success
        elif self.depreciation_level == 'parent_level':
            if self.parent:
                return self.parent.compute_depreciation_board()
        return False

    def set_to_draft(self):
        print("asset %s set to draft:" % self.id, self.state)
        # if asset in draft
        if self.state == 'draft':
            print("already")
            return
        #set asset to draft
        result =super(Assets, self).set_to_draft()

        # set parent to draft
        if self.parent:
            self.parent.set_to_draft()

        #set parts to draft
        for part in self.parts:
            part.set_to_draft()

        return result

    def set_to_running(self):
        # if asset in running or in use state
        if self.state in ('inuse', 'open'):
            return

        #run the asset
        result = None
        if self.depreciation_level == 'asset_level':
            result =  super(Assets, self).set_to_running()
        elif self.depreciation_level in ('parts_level', 'parent_level'):
            self.write({'state': 'inuse'})

        # run parent
        if self.parent:
            self.parent.set_to_running()

        # run parts
        for part in self.parts:
            part.set_to_running()
        return result

    def pause(self, pause_date):
        # if asset in paused
        if self.state == 'paused':
            return
        #pause the asset
        result = None
        if self.depreciation_level == 'asset_level':
            result = super(Assets, self).pause(pause_date)
        elif self.depreciation_level in ('parts_level', 'parent_level'):
            self.write({'state': 'paused'})

        self.message_post(body=_("Asset paused"))

        # pause parent
        if self.parent:
            self.parent.pause(pause_date)

        # pause parts
        for part in self.parts:
            part.pause(pause_date)

        return result

    @api.depends('custodians')
    def get_current_custodian(self):
        for record in self:
            record.current_custodian = record.custodians.search(
                [('end_responsibility', '=', False), ('asset_id', '=', record.id)], limit=1).responsible_person.name \
                if record.custodians.search([('end_responsibility', '=', False), ('asset_id', '=', record.id)], limit=1) \
                else "Not Assigned"

    def get_current_location(self):
        for record in self:
            record.location = self.env["stock.move.line"].search(
                [('product_id', '=', self.product_id.id),
                 ('lot_id','=',self.product_lots_serial.name)]
                , limit=1, order='date desc').location_dest_id

    def action_view_stock_move_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("altanmia_assets_tracking.asset_move_location_action")

        action['domain'] = [('product_id', '=', self.product_id.id),('lot_id','=',self.product_lots_serial.name)]#,
        return action


class AssetTag(models.Model):
    _name = "tanmia.assets.assets_tag"
    _description = "Add edit remove assets tag"

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    color = fields.Integer(string="Color")
    color_2 = fields.Char(string="Color")


class AssetModify(models.TransientModel):
    _inherit = 'asset.modify'

    def modify(self):
        if self.asset_id.depreciation_level == 'parts_level':
            for part in self.asset_id.parts:
                part.compute_depreciation_board()
        elif self.asset_id.depreciation_level == 'asset_level':
            super(AssetModify, self).modify()
