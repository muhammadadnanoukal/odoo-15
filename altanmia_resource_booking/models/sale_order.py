import logging
import random
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, models, fields, _
from odoo.http import request
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    booking_order = fields.Boolean(string="Is Booking Order", default=False)

    book_transaction_ids = fields.Many2many('payment.transaction', 'booking_order_transaction_rel', 'booking_order_id', 'transaction_id',
                                       string='Transactions', copy=False, readonly=True)

    def add_date(self, dates=None, **kwargs):
        """ Add or set product quantity, add_qty can be negative """

        if not dates and len(dates) < 1:
            request.session['booking_order_id'] = None
            raise UserError(_('No Booking date selected to create booking order.'))

        add_qty = len(dates)
        kwargs = kwargs.get('kwargs')
        prod_id = kwargs['product']
        set_qty = 0
        self.ensure_one()
        product_context = dict(self.env.context)
        product_context.setdefault('lang', self.sudo().partner_id.lang)
        SaleOrderLineSudo = self.env['sale.order.line'].sudo().with_context(product_context)
        # change lang to get correct name of attributes/values
        product_with_context = self.env['product.product'].with_context(product_context)
        product = product_with_context.browse(int(prod_id))

        try:
            if add_qty:
                add_qty = int(add_qty)
        except ValueError:
            add_qty = 1
        try:
            if set_qty:
                set_qty = int(set_qty)
        except ValueError:
            set_qty = 0
        quantity = 0
        order_line = False
        if self.state != 'draft':
            request.session['booking_order_id'] = None
            raise UserError(_('It is forbidden to modify a sales order which is not in draft status.'))

        # Create line if no line with product_id can be located
        if not order_line:
            if not product:
                raise UserError(_("The given product does not exist therefore it cannot be added to cart."))

            no_variant_attribute_values = kwargs.get('no_variant_attribute_values') or []
            received_no_variant_values = product.env['product.template.attribute.value'].browse([int(ptav['value']) for ptav in no_variant_attribute_values])
            received_combination = product.product_template_attribute_value_ids | received_no_variant_values
            product_template = product.product_tmpl_id

            # handle all cases where incorrect or incomplete data are received
            combination = product_template._get_closest_possible_combination(received_combination)

            # get or create (if dynamic) the correct variant
            product = product_template._create_product_variant(combination)

            if not product:
                raise UserError(_("The given combination does not exist therefore it cannot be added to cart."))

            product_id = product.id

            values = self._website_product_id_change(self.id, product_id, qty=1, **kwargs)

            # add no_variant attributes that were not received
            for ptav in combination.filtered(lambda ptav: ptav.attribute_id.create_variant == 'no_variant' and ptav not in received_no_variant_values):
                no_variant_attribute_values.append({
                    'value': ptav.id,
                })

            # save no_variant attributes values
            if no_variant_attribute_values:
                values['product_no_variant_attribute_value_ids'] = [
                    (6, 0, [int(attribute['value']) for attribute in no_variant_attribute_values])
                ]

            # add is_custom attribute values that were not received
            custom_values = kwargs.get('product_custom_attribute_values') or []
            received_custom_values = product.env['product.template.attribute.value'].browse([int(ptav['custom_product_template_attribute_value_id']) for ptav in custom_values])

            for ptav in combination.filtered(lambda ptav: ptav.is_custom and ptav not in received_custom_values):
                custom_values.append({
                    'custom_product_template_attribute_value_id': ptav.id,
                    'custom_value': '',
                })

            # set booking  date
            values['booking_events'] = [(6, 0, [d.id for d in dates])]

            # save is_custom attributes values
            if custom_values:
                values['product_custom_attribute_value_ids'] = [(0, 0, {
                    'custom_product_template_attribute_value_id': custom_value['custom_product_template_attribute_value_id'],
                    'custom_value': custom_value['custom_value']
                }) for custom_value in custom_values]

            # create the line
            order_line = SaleOrderLineSudo.create(values)


            try:
                order_line._compute_tax_id()
            except ValidationError as e:
                # The validation may occur in backend (eg: taxcloud) but should fail silently in frontend
                _logger.debug("ValidationError occurs during tax compute. %s" % (e))
            if add_qty:
                add_qty -= 1

        # compute new quantity
        if set_qty:
            quantity = set_qty
        elif add_qty is not None:
            quantity = order_line.product_uom_qty + (add_qty or 0)

        # Remove zero of negative lines
        if quantity <= 0:
            linked_line = order_line.linked_line_id
            order_line.unlink()
            if linked_line:
                # update description of the parent
                linked_product = product_with_context.browse(linked_line.product_id.id)
                linked_line.name = linked_line.get_sale_order_line_multiline_description_sale(linked_product)
        else:
            # update line
            no_variant_attributes_price_extra = [ptav.price_extra for ptav in order_line.product_no_variant_attribute_value_ids]
            values = self.with_context(no_variant_attributes_price_extra=tuple(no_variant_attributes_price_extra))._website_product_id_change(self.id, product_id, qty=quantity, **kwargs)
            order = self.sudo().browse(self.id)
            if self.pricelist_id.discount_policy == 'with_discount' and not self.env.context.get('fixed_price'):
                product_context.update({
                    'partner': order.partner_id,
                    'quantity': quantity,
                    'date': order.date_order,
                    'pricelist': order.pricelist_id.id,
                })
            product_with_context = self.env['product.product'].with_context(product_context).with_company(order.company_id.id)
            product = product_with_context.browse(product_id)

            order_line.write(values)

            # link a product to the sales order
            if kwargs.get('linked_line_id'):
                linked_line = SaleOrderLineSudo.browse(kwargs['linked_line_id'])
                order_line.write({
                    'linked_line_id': linked_line.id,
                })
                linked_product = product_with_context.browse(linked_line.product_id.id)
                linked_line.name = linked_line.get_sale_order_line_multiline_description_sale(linked_product)
            # Generate the description with everything. This is done after
            # creating because the following related fields have to be set:
            # - product_no_variant_attribute_value_ids
            # - product_custom_attribute_value_ids
            # - linked_line_id
            order_line.name = order_line.get_sale_order_line_multiline_description_sale(product)

        option_lines = self.order_line.filtered(lambda l: l.linked_line_id.id == order_line.id)
        
        return {'line_id': order_line.id, 'quantity': quantity, 'option_ids': list(set(option_lines.ids))}

    def get_portal_last_book_transaction(self):
        self.ensure_one()
        return self.book_transaction_ids._get_last()

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        super(SaleOrder, self).onchange_partner_id()
        for line in self.order_line:
            for event in line.booking_events:
                event.partner_id = self.partner_id

    def make_reservation(self):
        for order in self:
            for line in order.with_context(active_test=False).order_line:
                for event in line.booking_events:
                    event.write({'active':True})

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    booking_events = fields.One2many('calendar.event', 'order_line',  domain=['|',('active','=',False),('active','=',True)])
