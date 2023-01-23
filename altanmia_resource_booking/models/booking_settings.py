from odoo import fields, models, api


class BookingSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    max_multi_booking_number = fields.Integer(string='Max Booking number',
                                    default=10,
                                    help="Max reservation number that user can do in one booking order")

    def set_values(self):
        res = super(BookingSetting, self).set_values()
        config_parameters = self.env['ir.config_parameter']
        config_parameters.set_param("max_multi_booking_number", self.max_multi_booking_number)
        return res

    @api.model
    def get_values(self):
        res = super(BookingSetting, self).get_values()
        max_multi_booking_number = self.env['ir.config_parameter'].get_param('max_multi_booking_number')
        if not max_multi_booking_number:
            max_multi_booking_number = 10
        res.update(max_multi_booking_number=max_multi_booking_number)

        return res
