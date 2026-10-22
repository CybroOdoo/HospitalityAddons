# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2026-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

RESERVATION_MODEL = 'hospitality.reservation'
RESERVATION_CHECKED_IN_STATE = 'checked_in'
RESERVATION_CHECKED_OUT_STATE = 'checked_out'

CREDIT_BY_TASK_TYPE = {
    'departure': 4,
    'stayover': 2,
    'arrival_check': 1,
    'turndown': 1,
    'deep_clean': 8,
}
DEFAULT_CREDIT = 2

INSPECT_SPACE_STATUS_BY_TASK_TYPE = {
    'departure': 'vacant_clean',
    'stayover': 'occupied_clean',
}

STATE_TRANSITION_ACTIONS = {
    ('pending', 'in_progress'): 'action_assign',
    ('in_progress', 'done'): 'action_finish',
    ('done', 'inspected'): 'action_inspect',
    ('in_progress', 'dnd'): 'action_set_dnd',
    ('dnd', 'pending'): 'action_clear_dnd',
}


class HospitalityHousekeepingTask(models.Model):
    """A single housekeeping job on a space for a business date, with
    a small state machine covering assignment, completion, inspection
    and the dnd/refusal side paths."""
    _name = 'hospitality.housekeeping.task'
    _description = 'Housekeeping Task'
    _inherit = ['mail.thread', 'hospitality.mixin.property']
    _order = 'priority desc, business_date, space_id'
    _rec_name = 'name'

    _unique_task_per_space_date_type = models.Constraint(
        'unique (space_id, business_date, task_type)',
        'A task of this type already exists for this space on this '
        'business date.',
    )

    name = fields.Char(
        string='Name', compute='_compute_name', store=True,
        help='Readable label for this task, e.g. "Room 102 - '
             'Arrival Check - 07/06/2026". Used for breadcrumbs, '
             'chatter, and anywhere the task is referenced by name.')
    property_id = fields.Many2one(
        'hospitality.property', string='Property', required=True,
        index=True,help="The hospitality property where this task is being performed.",)
    space_id = fields.Many2one(
        'hospitality.space', string='Room', required=True, index=True,
        help="The specific room, suite, or room where housekeeping work "
             "needs to be done.",
    )
    space_type_id = fields.Many2one(
        'hospitality.space.type', string='Room Type',
        related='space_id.space_type_id', store=True, index=True,
        help='Stored so the HK Status pivot (HK-05) can group by it '
             'directly; pivot/read_group need a real field on this '
             'model, not a dotted path through space_id.')
    business_date = fields.Date(
        required=True, default=lambda self: self._default_business_date(),
        help="The business date for which this task is scheduled. Defaults "
             "to the property's current business date or today's date.",
    )
    task_type = fields.Selection([
        ('stayover', 'Stayover'),
        ('departure', 'Departure'),
        ('arrival_check', 'Arrival Check'),
        ('turndown', 'Turndown'),
        ('deep_clean', 'Deep Clean'),
        ('oo_release', 'Out-of-Order Release'),
        ('custom', 'Custom'),
    ], required=True,
        help="The type of housekeeping work required. Different task types "
             "have different credit values and post-inspection status updates.",
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('inspected', 'Inspected'),
        ('dnd', 'Do Not Disturb'),
        ('refused', 'Refused'),
    ], required=True, default='pending', tracking=True,
        help="Current state of the task in the housekeeping workflow. "
             "Tasks progress through: Pending -> In Progress -> Done -> "
             "Inspected, with DND and Refused as side paths.",
    )
    attendant_user_id = fields.Many2one(
        'res.users', string='Attendant (User)',
        help='Set when the attendant is an Odoo user.')
    attendant_id = fields.Many2one(
        'hospitality.housekeeper', string='Attendant (Housekeeper)',
        help='Set instead of Attendant (User) when the attendant does '
             'not have an Odoo user account.')
    inspector_id = fields.Many2one('res.users', string='Inspector',
                                   help="The user who performed the quality inspection on this task.",
                                   )
    credit = fields.Integer(
        string='Credit', default=DEFAULT_CREDIT,
        help='Workload weight of this task, used to balance '
             'assignments across attendants.')
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('vip', 'VIP'),
        ('vip_high', 'VIP High'),
    ], default='normal',
        help="Priority level of the task, used for sorting and "
             "determining which tasks should be handled first.",
    )
    rush = fields.Boolean(default=False,string="Is a rush request?",
                          help="Flag indicating this task is a rush request and should "
                               "be prioritized over normal tasks.",
                          )
    started_at = fields.Datetime(string="Started at",
                                 help="Flag indicating this task is a rush request and should "
                                      "be prioritized over normal tasks.",
                                 )
    finished_at = fields.Datetime(string="Finished at",
                                  help="Timestamp when the task was completed (state changed to done).",
                                  )
    inspected_at = fields.Datetime(string="Inspected at",
                                   help="Timestamp when the task was inspected (state changed to inspected).",
                                   )
    notes = fields.Text(string='Notes',
                        help="Additional notes about the task, including special "
                             "instructions, guest requests, or issues encountered.",
                        )
    refusal_reason = fields.Text(string="Reason for refusal",
                                 help="Reason provided by the attendant for refusing to perform "
                                      "the task, recorded when the task is refused.",
                                 )

    def _default_business_date(self):
        """Default to the property's current business date. The
        property is normally known from context (e.g. the action that
        opens the board is scoped to a property); fall back to
        today's date if no property is available yet."""
        property_id = self.env.context.get('default_property_id')
        if property_id:
            return self.env['hospitality.property'].browse(
                property_id).business_date
        return fields.Date.context_today(self)

    def _compute_credit_default(self, task_type):
        """Return the default workload credit for a given task_type."""
        return CREDIT_BY_TASK_TYPE.get(task_type, DEFAULT_CREDIT)

    @api.depends('space_id', 'task_type', 'business_date')
    def _compute_name(self):
        """Compute a descriptive task name from the assigned space,
            task type, and business date."""
        task_type_labels = dict(
            self._fields['task_type'].selection)
        for task in self:
            space_name = task.space_id.display_name or _('New Room')
            task_type_label = task_type_labels.get(
                task.task_type, _('Task'))
            date_str = (
                fields.Date.to_string(task.business_date)
                if task.business_date else _('No Date'))
            task.name = f'{space_name} - {task_type_label} - {date_str}'

    @api.onchange('task_type')
    def _onchange_task_type(self):
        """Update the task credit automatically when the task type changes."""
        for task in self:
            task.credit = task._compute_credit_default(task.task_type)

    @api.model_create_multi
    def create(self, vals_list):
        """Assign default workload credits for new tasks before creating
            the records."""
        for vals in vals_list:
            if not vals.get('credit') and vals.get('task_type'):
                vals['credit'] = self._compute_credit_default(
                    vals['task_type'])
        return super().create(vals_list)

    def _ensure_state(self, expected_states):
        """Validate that all selected tasks are in one of the expected
            states before allowing a state transition."""
        wrong = self.filtered(lambda t: t.state not in expected_states)
        if wrong:
            raise UserError(_(
                'This action is not allowed from the current state of '
                'task(s): %s.') % ', '.join(wrong.mapped('display_name')))

    def action_assign(self, attendant_user_id=None, attendant_id=None):
        """pending -> in_progress. Exactly one of attendant_user_id /
        attendant_id must end up set.

        This can be called two ways:
        - Programmatically, passing attendant_user_id or attendant_id
          explicitly (e.g. from a wizard or another method).
        - From the plain "Assign" button on the form, which calls this
          with no arguments. In that case we fall back to whichever
          attendant field is already filled in on the record itself.
        """
        self._ensure_state(['pending'])
        for task in self:
            uid = (attendant_user_id if attendant_user_id is not None
                   else task.attendant_user_id.id)
            hk_id = (attendant_id if attendant_id is not None
                     else task.attendant_id.id)
            if bool(uid) == bool(hk_id):
                raise UserError(_(
                    'Provide either an attendant user or a housekeeper, '
                    'not both or neither.'))
            task.write({
                'state': 'in_progress',
                'started_at': fields.Datetime.now(),
                'attendant_user_id': uid or False,
                'attendant_id': hk_id or False,
            })
        return True

    def action_finish(self):
        """in_progress -> done."""
        self._ensure_state(['in_progress'])
        return self.write({
            'state': 'done',
            'finished_at': fields.Datetime.now(),
        })

    def action_inspect(self):
        """done -> inspected; updates the space status for task types
        that have a known post-inspection status (departure ->
        vacant_clean, stayover -> occupied_clean)."""
        self._ensure_state(['done'])
        for task in self:
            task.write({
                'state': 'inspected',
                'inspected_at': fields.Datetime.now(),
                'inspector_id': self.env.uid,
            })
            new_status = INSPECT_SPACE_STATUS_BY_TASK_TYPE.get(
                task.task_type)
            if new_status:
                task.space_id.write({'status': new_status})
        return True

    def action_set_dnd(self):
        """in_progress -> dnd.

        Calls super().write() directly (not self.write()): a bare
        {'state': ...} payload is intercepted by write() below and
        routed back into the matching action_* method for this
        transition -- which is this same method, so self.write()
        here would recurse forever.
        """
        self._ensure_state(['in_progress'])
        return super(HospitalityHousekeepingTask, self).write(
            {'state': 'dnd'})

    def action_clear_dnd(self):
        """dnd -> pending. See action_set_dnd() for why this calls
        super().write() instead of self.write()."""
        self._ensure_state(['dnd'])
        return super(HospitalityHousekeepingTask, self).write(
            {'state': 'pending'})

    def action_refuse(self, reason=None):
        """in_progress -> pending; records the refusal reason and
        frees up the task for reassignment."""
        self._ensure_state(['in_progress'])
        return self.write({
            'state': 'pending',
            'refusal_reason': reason,
            'attendant_user_id': False,
            'attendant_id': False,
            'started_at': False,
        })

    def write(self, vals):
        """Intercept bare state changes (as sent by kanban drag-
        between-states) and route them through the matching
        action_* method instead of writing 'state' directly, so a
        drag gets exactly the same validation and side effects
        (timestamps, space status, inspector stamping, ...) as
        clicking the equivalent form button.

        Any write that touches other fields alongside 'state' (e.g.
        a form save, or an internal write from one of the action_*
        methods themselves) is left alone and goes straight to
        super(), so this only special-cases the plain
        {'state': new_value} shape that a kanban drag produces.
        """
        if set(vals.keys()) == {'state'}:
            new_state = vals['state']
            for task in self:
                action_name = STATE_TRANSITION_ACTIONS.get(
                    (task.state, new_state))
                if not action_name:
                    raise UserError(_(
                        'Dragging task "%(task)s" from "%(from_state)s" '
                        'to "%(to_state)s" is not allowed.') % {
                            'task': task.display_name,
                            'from_state': task.state,
                            'to_state': new_state,
                        })
                getattr(task, action_name)()
            return True
        return super().write(vals)

    def _get_current_property_id(self):
        """Resolve the "current property" for the HK Board: the
        action's own context wins (e.g. a property switcher passing
        default_property_id), otherwise fall back to the first
        property assigned to the current user, matching the same
        user.property_ids convention used by the module's record
        rules. Returns False if neither is available (e.g. a user
        with no assigned property yet)."""
        property_id = self.env.context.get('default_property_id')
        if property_id:
            return property_id
        return self.env.user.property_ids[:1].id

    def _get_today_property_domain(self):
        """Domain scoped to the current property's own business_date
        (dynamic: advances only on night audit, not necessarily
        today's calendar date), or just today's calendar date across
        all properties if no property is resolvable yet. Shared by
        the HK Board, HK Status report, and the mobile API's "my
        tasks" endpoint so all three agree on what "today" means.

        Returns (domain, property_id) -- property_id may be False.
        """
        property_id = self._get_current_property_id()
        if property_id:
            business_date = self.env['hospitality.property'].browse(
                property_id).business_date
            domain = [
                ('business_date', '=', business_date),
                ('property_id', '=', property_id),
            ]
        else:
            domain = [
                ('business_date', '=', fields.Date.context_today(self)),
            ]
        return domain, property_id

    def action_hk_board(self):
        """Open the HK Board kanban, scoped to the current property's
        business date. Bound to a server action so the domain can be
        computed per-user at open time (business_date is dynamic:
        it's the property's own business_date, advanced only by
        night audit, not necessarily today's calendar date).

        Falls back to today's calendar date across all properties
        the user can see if no property is resolvable yet."""
        domain, property_id = self._get_today_property_domain()
        return {
            'name': _('HK Board'),
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.housekeeping.task',
            'view_mode': 'kanban,list,form',
            'views': [
                (self.env.ref(
                    'hospitality_housekeeping.view_hk_board_kanban').id,
                 'kanban'),
                (False, 'list'),
                (False, 'form'),
            ],
            'domain': domain,
            'context': {'default_property_id': property_id},
        }

    def action_open_space_form(self):
        """Floor plan link on the board card: opens the task's
        space directly. Swap the res_model/action for the real
        floor-plan view (e.g. the front desk tape chart) once that
        xmlid is available to this module."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.space',
            'res_id': self.space_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _attendant_sheet_sort_key(self):
        """Route order within an attendant's sheet: floor sequence,
        then floor code, then space code."""
        self.ensure_one()
        floor = self.space_id.floor_id
        return (floor.sequence, floor.code or '', self.space_id.code or '')

    def _get_attendant_sheet_groups(self):
        """Group self by attendant (user or housekeeper), each
        group's tasks sorted in floor -> space code route order.
        Returns a list of dicts: [{'attendant_name', 'tasks'}, ...],
        one entry per distinct attendant, ordered by attendant name.
        Tasks with no attendant set are grouped under 'Unassigned'.
        """
        groups = {}
        for task in self:
            attendant_name = (
                task.attendant_user_id.name
                or task.attendant_id.name
                or _('Unassigned'))
            groups.setdefault(attendant_name, self.browse())
            groups[attendant_name] |= task
        return [
            {
                'attendant_name': name,
                'tasks': tasks.sorted(
                    key=lambda t: t._attendant_sheet_sort_key()),
            }
            for name, tasks in sorted(groups.items())
        ]

    def action_hk_status_report(self):
        """Open the HK Status pivot (state x space_type_id), scoped
        to the current property's business date -- same "today"
        convention as the HK Board."""
        domain, _property_id = self._get_today_property_domain()
        return {
            'name': _('HK Status'),
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.housekeeping.task',
            'view_mode': 'pivot',
            'views': [
                (self.env.ref(
                    'hospitality_housekeeping.view_hk_status_pivot').id,
                 'pivot'),
            ],
            'domain': domain,
        }

    def _search_reservations(self, property_id, state):
        """Reservations in the given state, with a space assigned,
        for one property. See the RESERVATION_* constants at the top
        of this file for the schema this assumes."""
        return self.env[RESERVATION_MODEL].search([
            ('property_id', '=', property_id),
            ('state', '=', state),
            ('space_id', '!=', False),
        ])

    def _create_task_if_missing(self, prop, space, task_type):
        """Create a task of task_type for this space/business_date
        unless one already exists. Also enforced at the DB level by
        _unique_task_per_space_date_type; this pre-check just avoids
        a noisy IntegrityError on every cron run."""
        exists = self.search_count([
            ('space_id', '=', space.id),
            ('business_date', '=', prop.business_date),
            ('task_type', '=', task_type),
        ])
        if exists:
            return self.browse()
        return self.create({
            'property_id': prop.id,
            'space_id': space.id,
            'business_date': prop.business_date,
            'task_type': task_type,
        })

    @api.model
    def _cron_create_stayover_tasks(self):
        """Daily at 06:00: create a stayover task for every in-house
        room that doesn't already have one for today's business
        date. Skips the arrival day itself (no stayover needed the
        day a guest checks in) when a check_in_date field is present
        on the reservation to compare."""
        for prop in self.env['hospitality.property'].search(
                [('active', '=', True)]):
            reservations = self._search_reservations(
                prop.id, RESERVATION_CHECKED_IN_STATE)
            for reservation in reservations:
                if ('check_in_date' in reservation._fields
                        and reservation.check_in_date
                        == prop.business_date):
                    continue
                self._create_task_if_missing(
                    prop, reservation.space_id, 'stayover')

    @api.model
    def _cron_create_turndown_tasks(self):
        """Daily at 17:00: create a turndown task for every in-house
        room that doesn't already have one for today's business
        date. Skips the departure day itself (a departure task
        covers that room instead) when a check_out_date field is
        present on the reservation to compare."""
        for prop in self.env['hospitality.property'].search(
                [('active', '=', True)]):
            reservations = self._search_reservations(
                prop.id, RESERVATION_CHECKED_IN_STATE)
            for reservation in reservations:
                if ('check_out_date' in reservation._fields
                        and reservation.check_out_date
                        == prop.business_date):
                    continue
                self._create_task_if_missing(
                    prop, reservation.space_id, 'turndown')

    @api.model
    def _cron_create_departure_tasks(self):
        """Safety-net poll, every 15 minutes: creates a departure
        task for any space whose reservation is 'checked_out' and
        doesn't have one yet for today's business date.

        The primary path is now event-driven: write() on
        hospitality.reservation (see
        hospitality_reservation_hk_hook.py) fires
        _create_task_if_missing() immediately when a reservation's
        state transitions to 'checked_out' via action_check_out().
        This cron only matters if that transition happened some
        other way this hook doesn't see -- both routes share the
        same dedup check, so there's never a duplicate task."""
        for prop in self.env['hospitality.property'].search(
                [('active', '=', True)]):
            reservations = self._search_reservations(
                prop.id, RESERVATION_CHECKED_OUT_STATE)
            for reservation in reservations:
                self._create_task_if_missing(
                    prop, reservation.space_id, 'departure')