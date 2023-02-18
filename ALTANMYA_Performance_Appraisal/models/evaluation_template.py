from odoo import models, fields, api, _
import datetime
from datetime import timedelta

from odoo.exceptions import UserError


class EvaluationTemplate(models.Model):
    _name = 'evaluation.template'
    _description = 'Evaluation Template'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']

    user_id_number = fields.Integer('Current User ID', default=lambda self: self.env.user.id)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user.id, store=True)
    partner_id = fields.Many2one(related='user_id.partner_id')
    name = fields.Char(string='Name', readonly=True, required=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  domain=[('has_evaluation', '=', True)], store=True)
    qms_code = fields.Char('QMS Code')
    employee_user_id = fields.Integer('Employee User ID', compute='_compute_employee_user_id', store=True)

    # fields only for xml views
    appraiser_user_match = fields.Boolean(compute='_compute_match')
    hr_responsible_user_match = fields.Boolean(compute='_compute_match')
    employee_user_match = fields.Boolean(compute='_compute_match')

    @api.depends('appraiser_id')
    def _compute_match(self):
        for rec in self:
            if rec.appraiser_id == rec.user_id_number:
                rec.appraiser_user_match = True
            else:
                rec.appraiser_user_match = False
            if rec.employee_user_id == rec.user_id_number:
                rec.employee_user_match = True
            else:
                rec.employee_user_match = False
            if rec.hr_responsible_user_id == rec.user_id_number:
                rec.hr_responsible_user_match = True
            else:
                rec.hr_responsible_user_match = False

    is_user_creator = fields.Boolean(compute='_compute_is_user_creator', default=False)

    @api.depends('employee_id')
    def _compute_is_user_creator(self):
        for rec in self:
            if self.env.user.has_group('ALTANMYA_Performance_Appraisal.evaluation_group_creators'):
                rec.is_user_creator = True
            else:
                rec.is_user_creator = False

    show_comments_and_signature_page = fields.Boolean(compute='_compute_show_comments_and_signature_page',
                                                      default=False)

    @api.depends('appraiser_user_match', 'employee_user_match')
    def _compute_show_comments_and_signature_page(self):
        for rec in self:
            if self.env.user.has_group('ALTANMYA_Performance_Appraisal.evaluation_group_creators') \
                    or rec.appraiser_user_match or rec.employee_user_match:
                rec.show_comments_and_signature_page = True
            else:
                rec.show_comments_and_signature_page = False

    @api.depends('employee_id')
    def _compute_employee_user_id(self):
        for rec in self:
            if rec.employee_id.user_id:
                rec.employee_user_id = rec.employee_id.user_id.id
            else:
                rec.employee_user_id = 0

    appraiser_id = fields.Integer('Appraiser ID', compute='_compute_appraiser_id')

    @api.depends('employee_id')
    def _compute_appraiser_id(self):
        for rec in self:
            if rec.employee_id.parent_id:
                if rec.employee_id.parent_id.user_id:
                    rec.appraiser_id = rec.employee_id.parent_id.user_id.id
                else:
                    first_parent_manager_user_id = rec.get_first_parent_manager_user_id(rec.employee_id.parent_id)
                    if first_parent_manager_user_id != 0:
                        rec.appraiser_id = first_parent_manager_user_id
                    else:
                        rec.appraiser_id = rec.hr_responsible.id
            else:
                rec.appraiser_id = rec.hr_responsible.id

    def get_first_parent_manager_user_id(self, manager):
        if not manager.parent_id:
            return 0
        if manager.user_id:
            return manager.user_id.id
        return self.get_first_parent_manager_user_id(manager.parent_id)

    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id',
                                    readonly=True, store=True)
    management_id = fields.Many2one('hr.department', string='Management', related='department_id.parent_id', store=True)
    evaluation_period = fields.Integer(string='Evaluation Period', required=True, default=7, store=True)
    job_title = fields.Char(string='Job Title', related='employee_id.job_title', readonly=True, store=True)
    date = fields.Datetime(string='Date', default=fields.Datetime.now(), required=True, store=True)

    evaluation_template_id = fields.Many2one('evaluation.template.type',
                                             related='employee_id.evaluation_template_type_id',
                                             string='Evaluation Template Type', store=True)
    scoring_system = fields.Many2one(related='evaluation_template_id.scoring_system', store=True)
    overall_rate = fields.Char(compute='_compute_overall_rate', store=True)
    responsible_users_ids = fields.Many2many('res.users', 'evaluation_template_res_users_rel')
    hr_responsible = fields.Many2one('res.users', string='HR Responsible', related='employee_id.hr_responsible', store=True)
    hr_responsible_user_id = fields.Integer('HR Responsible ID', compute='_compute_hr_responsible_user_id', default=0)
    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('inform_hr', 'HR Informed')
    ], required=True, string='Status', readonly=True, copy=False, store=True, default='in_progress')

    def button_mark_as_done(self):
        if all([section.state == 'done' for section in self.section_ids]):
            self.state = 'done'
            if self.employee_user_id > 1:
                concerned_employees_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_concerned_employees')
                concerned_employees_group.sudo().write({'users': [(4, self.employee_user_id)]})
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': _('\nNot all sections are set to done.\n'),
                    'sticky': False,
                    'type': 'danger',
                }
            }

    def button_inform_hr(self):
        self.state = 'inform_hr'
        category_id = self.env.ref('ALTANMYA_Performance_Appraisal.calendar_event_employee_evaluation').id
        self.env['calendar.event'].create({
            'name': f"Evaluation has been done for employee ({self.employee_id.name}).",
            'start': fields.Datetime.to_string(datetime.datetime.now().replace(second=0)),
            'stop': fields.Datetime.to_string(datetime.datetime.now().replace(second=0) + timedelta(hours=2)),
            'allday': False,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'evaluation.template')]).id,
            'res_id': self.id,
            'partner_ids': [(4, self.hr_responsible.partner_id.id)],
            'user_id': self.user_id_number,
            'categ_ids': [(4, category_id)],
            'alarm_ids': [
                (0, 0, {
                    'name': 'Notification - 15 Minutes',
                    'alarm_type': 'notification',
                    'interval': 'minutes',
                    'duration': 30,
                }), (0, 0, {
                    'name': 'Email - 1 Hours',
                    'alarm_type': 'email',
                    'interval': 'hours',
                    'duration': 1,
                }), (0, 0, {
                    'name': 'SMS Text Message - 1 Hours',
                    'alarm_type': 'sms',
                    'interval': 'hours',
                    'duration': 1,
                })]
        })

    def button_reset_to_draft(self):
        self.state = 'in_progress'

    @api.depends('hr_responsible')
    def _compute_hr_responsible_user_id(self):
        for rec in self:
            if rec.hr_responsible:
                rec.hr_responsible_user_id = rec.hr_responsible.id
            else:
                rec.hr_responsible_user_id = 0

    @api.onchange('evaluation_template_id')
    def _onchange_evaluation_template_id(self):
        self._prepare_section_ids_values()

    def unlink(self):
        self.mapped('section_ids').unlink()
        return super(EvaluationTemplate, self).unlink()

    def _link_responsible_user_to_group(self, responsible_user, responsibility_type):
        if responsibility_type == 'manager':
            if not self.env['res.users'].browse(responsible_user).has_group('ALTANMYA_Performance_Appraisal.evaluation_group_managers'):
                managers_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_managers')
                managers_group.sudo().write({'users': [(4, responsible_user)]})
        elif responsibility_type == 'hr':
            if not self.env['res.users'].browse(responsible_user).has_group('ALTANMYA_Performance_Appraisal.evaluation_group_hr'):
                hr_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_hr')
                hr_group.sudo().write({'users': [(4, responsible_user)]})
        elif responsibility_type == 'specific_user':
            if not self.env['res.users'].browse(responsible_user).has_group('ALTANMYA_Performance_Appraisal.evaluation_group_specific_users'):
                specific_users_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_specific_users')
                specific_users_group.sudo().write({'users': [(4, responsible_user)]})

    def _prepare_section_ids_values(self):
        for section in self.section_ids:
            section.unlink()
        for section in self.evaluation_template_id.section_ids:
            responsible_user_id = self._compute_responsible_user(section)
            self._link_responsible_user_to_group(responsible_user_id, section.evaluation_responsibility)
            self.responsible_users_ids = [(4, responsible_user_id)]
            new_section = self.env['evaluation.section'].create({
                'section_type_id': section.section_type_id.id,
                'weight': section.weight,
                'evaluation_template_id': self.id,
                'section_responsible_user_id': responsible_user_id,
            })
            for line in section.section_line_ids:
                self.env['evaluation.section.line'].create({
                    'criterion_id': line.criterion_id.id,
                    'weight': line.weight,
                    'section_id': new_section.id
                })

    def read(self, fields=None, load='_classic_read'):
        res = super(EvaluationTemplate, self).read(fields=fields, load=load)
        for rec in self:
            rec._compute_hr_responsible_user_id()
            rec._compute_appraiser_id()
            rec._compute_employee_user_id()
            rec._compute_one_field_required()
            for evtt_section in rec.evaluation_template_id.section_ids:
                for evt_section in rec.section_ids:
                    if evt_section.section_type_id.id == evtt_section.section_type_id.id:
                        evt_section.section_responsible_user_id = rec._compute_responsible_user(evtt_section)
                        break
        if 'section_ids' in res[0]:
            if self.env.user.has_group('ALTANMYA_Performance_Appraisal.evaluation_group_creators'):
                return res
            section_ids = res[0]['section_ids']
            filtered_section_ids = []
            if len(section_ids) != 0:
                recs = self.env['evaluation.section'].browse(section_ids)
                for rec in recs:
                    if rec.section_responsible_user_id.id == self.env.user.id:
                        filtered_section_ids.append(rec.id)
                res[0]['section_ids'] = filtered_section_ids
        return res

    def _compute_responsible_user(self, section):
        result = False
        if section.evaluation_responsibility == 'manager':
            result = self.employee_id.parent_id.user_id.id
        elif section.evaluation_responsibility == 'hr':
            result = self.employee_id.hr_responsible.id
        elif section.evaluation_responsibility == 'specific_user':
            result = section.specific_user.id
        result = result or self.env['res.users'].search(
            [('groups_id', 'in', [self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_creators').id])],
            limit=1).id
        return result

    @api.depends('scoring_system')
    def _compute_overall_rate(self):
        for rec in self:
            pairs = sorted(rec.scoring_system.score_pair_ids, key=lambda l: l.score)
            for pair in pairs:
                if rec.overall_score == pair.score:
                    rec.overall_rate = pair.rate
                    return

    section_ids = fields.One2many('evaluation.section', 'evaluation_template_id', store=True)
    overall_score = fields.Float(string='Overall Score', compute='_compute_overall_score', default=0.0)
    evaluation_type = fields.Selection(related='evaluation_template_id.evaluation_type')

    no_of_absent_days = fields.Integer(string='Number of Absent Days', default=0)
    no_of_delay = fields.Integer(string='Number of Delay', default=0)
    no_of_verbal_warnings = fields.Integer(string='Number of Verbal Warnings', default=0)
    no_of_sick_days = fields.Integer(string='Number of Sick Days', default=0)
    no_of_early_leave = fields.Integer(string='Number of Early Leave', default=0)
    no_of_written_warnings = fields.Integer(string='Number of Written Warnings', default=0)
    no_of_absent_hours = fields.Integer(string='Number of Absent Hours', default=0)
    no_of_unpaid_days = fields.Integer(string='Number of Unpaid Days', default=0)
    no_of_deviations = fields.Integer(string='Number of Deviations', default=0)

    suggestion_improvements = fields.Html(string='Suggestion Improvements', store=True)
    appraiser_comments = fields.Html(string='Appraiser Comments', store=True)
    appraiser_signature = fields.Binary(string='Appraiser Signature', store=True)
    concerned_employee_comments = fields.Html(string='Concerned Employee Comments', store=True)
    concerned_employee_signature = fields.Binary(string='Concerned Employee Signature', store=True)
    recommendations = fields.Html(string='Recommendations', store=True)

    score_note_selection = fields.Selection(related='evaluation_template_id.score_note_selection',
                                            string='Write Notes or Upload a Document',
                                            help="Technical field for UX purpose.", store=True)
    score_note = fields.Html(string='Notes on Low/High Score', store=True)
    score_attachment = fields.Binary(string='Upload Attachment', store=True)
    one_field_required = fields.Boolean(compute='_compute_one_field_required', default=True)

    @api.depends('evaluation_template_id')
    def _compute_one_field_required(self):
        for rec in self:
            if (not rec.score_note or rec.score_note == '<p><br></p>') and not rec.score_attachment:
                rec.one_field_required = True
            else:
                rec.one_field_required = False

    @api.onchange('score_note', 'score_attachment')
    def _onchange_score_notes(self):
        for rec in self:
            if not rec.score_attachment and (not rec.score_note or rec.score_note == '<p><br></p>'):
                rec.one_field_required = True
            else:
                rec.one_field_required = False

    @api.depends('section_ids')
    def _compute_overall_score(self):
        for rec in self:
            if not rec.section_ids:
                rec.overall_score = 0.0
            for section in rec.section_ids:
                rec.overall_score += section.final_score
            rec.overall_score = rec.overall_score / 100
            result = rec.overall_score
            if result <= 70:
                result = 60
            elif 70 < result <= 90:
                result = 80
            elif 90 < result <= 105:
                result = 100
            elif 105 < result <= 120:
                result = 110
            else:
                result = 130
            rec.overall_score = result
            rec._compute_overall_rate()

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            seq_name = self.env['ir.sequence'].next_by_code('evaluation.template')
            vals['name'] = seq_name or _('New')
        result = super(EvaluationTemplate, self).create(vals)
        return result

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super(EvaluationTemplate, self).copy(default=default)

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'section_ids' not in default:
            default['section_ids'] = [(0, 0, line.copy_data()[0]) for line in self.section_ids]
        return super(EvaluationTemplate, self).copy_data(default)

    def get_department_head(self, department_id):
        if not department_id.parent_id:
            return department_id.id
        return self.get_department_head(department_id.parent_id)

    def _reset_evaluators_groups(self):
        employees_to_evaluate = self.env['hr.employee'].search([
            ('has_evaluation', '=', True),
            ('parent_id', '!=', False),
            ('department_id', '!=', False),
            ('evaluation_template_type_id', '!=', False),
            ('hr_responsible', '!=', False)
        ])

        employees_has_evaluation = self.env['hr.employee'].search([
            ('has_evaluation', '=', True)])

        if len(employees_has_evaluation) != len(employees_to_evaluate):
            return '_', '_'

        if len(employees_to_evaluate) == 0:
            return None, None

        employees_to_evaluate_departments = employees_to_evaluate.mapped('department_id')
        concerned_departments_ids = []
        for department in employees_to_evaluate_departments:
            concerned_departments_ids.append(self.get_department_head(department))

        departments_heads = self.env['hr.employee'].search([
            ('department_id', 'in', concerned_departments_ids),
            ('department_id.parent_id', '=', False),
            ('parent_id', '=', False)
        ])

        direct_managers = employees_to_evaluate.mapped('parent_id')
        direct_managers_and_departments_heads = direct_managers + departments_heads

        managers_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_managers')
        group_user_ids = managers_group.users.ids
        managers_group.sudo().write({'users': [(3, user) for user in group_user_ids]})
        managers_group.sudo().write({'users': [(4, manager.user_id.id) for manager in
                                               direct_managers_and_departments_heads if manager.user_id]})

        hr_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_hr')
        group_user_ids = hr_group.users.ids
        hr_group.sudo().write({'users': [(3, user) for user in group_user_ids]})

        specific_users_group = self.env.ref('ALTANMYA_Performance_Appraisal.evaluation_group_specific_users')
        group_user_ids = specific_users_group.users.ids
        specific_users_group.sudo().write({'users': [(3, user) for user in group_user_ids]})

        return employees_to_evaluate, direct_managers_and_departments_heads

    def action_start_evaluation(self):
        employees_to_evaluate, direct_managers_and_departments_heads = self._reset_evaluators_groups()

        if employees_to_evaluate is None and direct_managers_and_departments_heads is None:
            raise UserError(_('There is not any employees to evaluate.'))

        elif employees_to_evaluate is '_' and direct_managers_and_departments_heads is '_':
            raise UserError(_('Please make sure that you have set all the configurations needed for the employees.\nDepartment, Manager and the Evaluation Configurations.'))

        for employee in employees_to_evaluate:
            evt = self.env['evaluation.template'].create({'employee_id': employee.id})
            evt._onchange_evaluation_template_id()

        category_id = self.env.ref('ALTANMYA_Performance_Appraisal.calendar_event_employee_evaluation').id
        for manager in direct_managers_and_departments_heads:
            partner_manager = self.env['res.partner'].search([('user_id', '=', manager.user_id.id)])
            if manager.user_id.id and partner_manager:
                self.env['calendar.event'].create({
                    'name': 'Employees evaluation started.\nPlease check. From the Employee Evaluation menu.',
                    'start': fields.Datetime.to_string(datetime.datetime.now().replace(second=0)),
                    'stop': fields.Datetime.to_string(datetime.datetime.now().replace(second=0) + timedelta(hours=2)),
                    'allday': False,
                    'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'evaluation.template')]).id,
                    'partner_ids': [(4, self.env.user.partner_id.id), (4, partner_manager.id)],
                    'user_id': manager.user_id.id,
                    'categ_ids': [(4, category_id)],
                    'alarm_ids': [
                        (0, 0, {
                            'name': 'Notification - 15 Minutes',
                            'alarm_type': 'notification',
                            'interval': 'minutes',
                            'duration': 30,
                        }), (0, 0, {
                            'name': 'Email - 1 Hours',
                            'alarm_type': 'email',
                            'interval': 'hours',
                            'duration': 1,
                        }), (0, 0, {
                            'name': 'SMS Text Message - 1 Hours',
                            'alarm_type': 'sms',
                            'interval': 'hours',
                            'duration': 1,
                        })]
                })
        self.env['calendar.event'].create({
            'name': 'Employees evaluations have been created.',
            'start': fields.Datetime.to_string(datetime.datetime.now().replace(second=0)),
            'stop': fields.Datetime.to_string(datetime.datetime.now().replace(second=0) + timedelta(hours=2)),
            'allday': False,
            'res_model_id': self.env['ir.model'].sudo().search([('model', '=', 'evaluation.template')]).id,
            'partner_ids': [(4, self.env.user.partner_id.id)],
            'user_id': self.user_id_number,
            'categ_ids': [(4, category_id)],
            'alarm_ids': [
                (0, 0, {
                    'name': 'Notification - 15 Minutes',
                    'alarm_type': 'notification',
                    'interval': 'minutes',
                    'duration': 30,
                }), (0, 0, {
                    'name': 'Email - 1 Hours',
                    'alarm_type': 'email',
                    'interval': 'hours',
                    'duration': 1,
                }), (0, 0, {
                    'name': 'SMS Text Message - 1 Hours',
                    'alarm_type': 'sms',
                    'interval': 'hours',
                    'duration': 1,
                })]
        })
