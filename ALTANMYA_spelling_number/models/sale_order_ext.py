from deep_translator import GoogleTranslator
from odoo import api, models, fields, _
from num2words import num2words
import inflect


class SaleOrderSpelling(models.Model):
    _inherit = 'sale.order'

    spelling_total_en = fields.Text(compute='_compute_spelling_en', string='Spelling English')
    spelling_total_ar = fields.Text(compute='_compute_spelling_ar', string='Spelling Arabic')

    def get_total_from_invoice_info(self, invoice_info):
        if invoice_info:
            first_comma_index = invoice_info.find(',')
            float_total = float(invoice_info[17:first_comma_index])
            float_total = round(float_total, 2)
            return float_total
        return False

    def get_spelling_num(self, num: float, lang='en', currency_unit='Dollars', currency_subunit='Cents'):
        integer_part = int(num)
        decimal_part = round((num - integer_part), 2) * 100
        decimal_part = int(decimal_part)
        p = inflect.engine()
        num_spell = ''

        if lang == 'en':
            integer_spell = p.number_to_words(integer_part) + ' ' + currency_unit
            decimal_spell = p.number_to_words(decimal_part) + ' ' + currency_subunit
            num_spell = integer_spell + ' And ' + decimal_spell
            num_spell = num_spell.title()

        elif lang == 'ar':
            integer_spell = num2words(integer_part, lang='ar') + ' ' + currency_unit
            decimal_spell = num2words(decimal_part, lang='ar') + ' ' + currency_subunit
            num_spell = integer_spell + ' و ' + decimal_spell

        return num_spell

    @api.depends('tax_totals_json')
    def _compute_spelling_en(self):
        self.spelling_total_en = ''

        total = self.get_total_from_invoice_info(self.tax_totals_json)

        if total:
            en_currency_unit = self.currency_id.currency_unit_label
            en_currency_subunit = self.currency_id.currency_subunit_label
            self.spelling_total_en = self.get_spelling_num(total, lang='en',
                                                           currency_unit=en_currency_unit,
                                                           currency_subunit=en_currency_subunit)

    @api.depends('tax_totals_json')
    def _compute_spelling_ar(self):
        self.spelling_total_ar = ''

        total = self.get_total_from_invoice_info(self.tax_totals_json)

        if total:
            ar_currency_unit = GoogleTranslator(source='auto', target='ar').translate(
                self.currency_id.currency_unit_label)
            ar_currency_subunit = GoogleTranslator(source='auto', target='ar').translate(
                self.currency_id.currency_subunit_label)
            if self.currency_id.id == 136:
                ar_currency_unit = 'ليرة سورية'
                ar_currency_subunit = 'قرش'
            self.spelling_total_ar = self.get_spelling_num(total, lang='ar',
                                                           currency_unit=ar_currency_unit,
                                                           currency_subunit=ar_currency_subunit)
