# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

class Question(models.Model):
    _name = "tanmia.booking.question"
    _description = "Resource Booking : Questions"
    _order = "sequence"

    sequence = fields.Integer('Sequence')
    book_profile_id = fields.Many2one('tanmia.booking.book.profile', 'Appointment Type', ondelete="cascade")
    name = fields.Char('Question', translate=True, required=True)
    placeholder = fields.Char('Placeholder', translate=True)
    question_required = fields.Boolean('Required Answer')
    question_type = fields.Selection([
        ('char', 'Single line text'),
        ('text', 'Multi-line text'),
        ('select', 'Dropdown (one answer)'),
        ('radio', 'Radio (one answer)'),
        ('checkbox', 'Checkboxes (multiple answers)')], 'Question Type', default='char')
    answer_ids = fields.Many2many('tanmia.booking.answer', 'tanmia_booking_question_answer_rel', 'question_id', 'answer_id', string='Available Answers')


class Answer(models.Model):
    _name = "tanmia.booking.answer"
    _description = "Resource Booking : Answers"

    question_id = fields.Many2many('tanmia.booking.question', 'tanmia_booking_question_answer_rel', 'answer_id', 'question_id', string='Questions')
    name = fields.Char('Answer', translate=True, required=True)
