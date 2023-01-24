from deep_translator import GoogleTranslator
from odoo import api, models, fields, _
from num2words import num2words
import inflect


class AccountMoveSpelling(models.Model):
    _inherit = 'account.move'

    spelling_amount_en = fields.Text(compute='_compute_spelling_en', string='Spelling English')
    spelling_amount_ar = fields.Text(compute='_compute_spelling_ar', string='Spelling Arabic')

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

    @api.depends('amount_residual')
    def _compute_spelling_en(self):
        self.spelling_amount_en = ''

        amount = 0.0
        if self.amount_residual:
            amount = float(self.amount_residual)
            amount = round(amount, 2)

        if amount > 0:
            en_currency_unit = self.currency_id.currency_unit_label
            en_currency_subunit = self.currency_id.currency_subunit_label
            self.spelling_amount_en = self.get_spelling_num(amount, lang='en',
                                                            currency_unit=en_currency_unit,
                                                            currency_subunit=en_currency_subunit)

    @api.depends('amount_residual')
    def _compute_spelling_ar(self):
        self.spelling_amount_ar = ''

        amount = 0.0
        if self.amount_residual:
            amount = float(self.amount_residual)
            amount = round(amount, 2)

        if amount > 0:
            ar_currency_unit = GoogleTranslator(source='auto', target='ar').translate(
                self.currency_id.currency_unit_label)
            ar_currency_subunit = GoogleTranslator(source='auto', target='ar').translate(
                self.currency_id.currency_subunit_label)
            if self.currency_id.id == 136:
                ar_currency_unit = 'ليرة سورية'
                ar_currency_subunit = 'قرش'
            self.spelling_amount_ar = self.get_spelling_num(amount, lang='ar',
                                                            currency_unit=ar_currency_unit,
                                                            currency_subunit=ar_currency_subunit)
