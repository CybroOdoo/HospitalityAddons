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
from odoo.tools import _
from odoo.exceptions import UserError

_ALLOWED_FROM = {
    'action_open': ('draft',),
    'action_start': ('open',),
    'action_hold': ('in_progress',),
    'action_await_part': ('in_progress',),
    'action_resume': ('on_hold', 'awaiting_part'),
    'action_done': ('in_progress',),
}

_AGE_BUCKET_TERMINAL_STATES = ('done', 'cancelled')


class HospitalityWorkOrder(models.Model):
    """Manages maintenance work orders for hospitality properties.
    Tracks maintenance requests from creation through completion,
    including assignment, workflow state transitions, labor and
    parts costs, out-of-order room handling, work order aging,
    and preventive maintenance generated from PPM templates.
    """
    _name = 'hospitality.work.order'
    _description = 'Hospitality Maintenance Work Order'
    _inherit = ['mail.thread', 'hospitality.mixin.property']
    _order = 'priority desc, reported_at desc'

    name = fields.Char(readonly=True, copy=False, default=lambda self: _('New'))
    property_id = fields.Many2one(
        'hospitality.property', required=True, index=True)
    # Explicit string: without it Odoo derives the label from the
    # field NAME and shows "Space", which no amount of relabelling
    # elsewhere would have corrected.
    space_id = fields.Many2one('hospitality.space', string='Room')
    area_label = fields.Char(
        help="Free-text location when the issue is not tied to a "
             "specific space (corridor, lobby, back-of-house, etc.).")
    asset_id = fields.Many2one('hospitality.asset')
    category = fields.Selection([
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('hvac', 'HVAC'),
        ('carpentry', 'Carpentry'),
        ('paint', 'Paint'),
        ('it', 'IT'),
        ('fire_safety', 'Fire Safety'),
        ('elevator', 'Elevator'),
        ('pool', 'Pool'),
        ('garden', 'Garden'),
        ('general', 'General'),
    ], required=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
        ('guest_blocking', 'Guest Blocking'),
    ], default='normal')
    reported_by = fields.Many2one(
        'res.users', default=lambda self: self.env.user)
    reported_at = fields.Datetime(default=fields.Datetime.now)
    source = fields.Selection([
        ('staff', 'Staff'),
        ('guest', 'Guest'),
        ('hk', 'Housekeeping'),
        ('sensor', 'Sensor'),
        ('ppm', 'PPM'),
    ], required=True, default='staff')
    description = fields.Text(required=True)
    photos = fields.Many2many(
        'ir.attachment', 'wo_photo_rel', 'work_order_id', 'attachment_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('awaiting_part', 'Awaiting Part'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], required=True, default='draft', tracking=True)
    assigned_user_id = fields.Many2one('res.users')
    vendor_partner_id = fields.Many2one('res.partner')
    estimated_hours = fields.Float()
    actual_hours = fields.Float()
    parts_used_ids = fields.One2many(
        'hospitality.work.order.part', 'work_order_id')
    currency_id = fields.Many2one(
        'res.currency', related='property_id.company_id.currency_id',
        store=True, readonly=True)
    cost_total = fields.Monetary(
        compute='_compute_cost_total', store=True, currency_field='currency_id')
    set_ooo = fields.Boolean(
        default=False,
        help="If checked, starting this work order automatically takes "
             "the space out of inventory (OOO).")
    ooo_from = fields.Date()
    ooo_to = fields.Date()
    notes = fields.Html()
    age_bucket = fields.Selection([
        ('1_lt_1d', '< 1 Day'),
        ('2_1_3d', '1-3 Days'),
        ('3_3_7d', '3-7 Days'),
        ('4_7_14d', '7-14 Days'),
        ('5_gt_14d', '> 14 Days'),
    ], compute='_compute_age_bucket', string='Age Bucket', store=True)

    @api.depends('reported_at', 'state')
    def _compute_age_bucket(self):
        """Computes the work order aging bucket based on its creation date."""
        now = fields.Datetime.now()
        for order in self:
            if order.state in _AGE_BUCKET_TERMINAL_STATES \
                    or not order.reported_at:
                order.age_bucket = False
                continue
            age_days = (now - order.reported_at).total_seconds() / 86400.0
            if age_days < 1:
                order.age_bucket = '1_lt_1d'
            elif age_days < 3:
                order.age_bucket = '2_1_3d'
            elif age_days < 7:
                order.age_bucket = '3_3_7d'
            elif age_days < 14:
                order.age_bucket = '4_7_14d'
            else:
                order.age_bucket = '5_gt_14d'

    @api.model
    def _cron_recompute_wo_age_buckets(self):
        """Periodic forced recompute of the stored age_bucket field for
        every non-terminal work order — see the field comment above for
        why this is needed at all (age advances with the clock, not with
        a write)."""
        active_orders = self.search([
            ('state', 'not in', _AGE_BUCKET_TERMINAL_STATES),
        ])
        active_orders._compute_age_bucket()

    @api.depends('parts_used_ids.qty', 'parts_used_ids.cost')
    def _compute_cost_total(self):
        """Computes the total cost of the work order from all parts used."""
        for order in self:
            order.cost_total = sum(
                line.qty * line.cost for line in order.parts_used_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Creates work orders and assigns a sequence number when required."""
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hospitality.work.order') or _('New')
        return super().create(vals_list)

    def _check_transition(self, method_name):
        """Validates that the current state allows the requested workflow transition."""
        allowed_states = _ALLOWED_FROM[method_name]
        invalid = self.filtered(lambda o: o.state not in allowed_states)
        if invalid:
            raise UserError(_(
                "Cannot perform this action on work order(s) %s: "
                "current state does not allow it.") % ', '.join(invalid.mapped('name')))

    def action_open(self):
        """Transitions draft work orders to the Open state."""
        self._check_transition('action_open')
        self.write({'state': 'open'})

    def action_start(self):
        """Starts the work order and optionally marks the related space as out of order."""
        self._check_transition('action_start')
        for order in self:
            if order.set_ooo and order.space_id:
                if not order.ooo_from or not order.ooo_to:
                    raise UserError(_(
                        "Set the OOO From/To dates before starting a work "
                        "order that blocks the room."))
                order.space_id.write({
                    'status': 'ooo',
                    'ooo_reason': order.description,
                    'ooo_from': order.ooo_from,
                    'ooo_to': order.ooo_to,
                })
            order.write({'state': 'in_progress'})

    def action_hold(self, reason=False):
        """Places the work order on hold and optionally logs the reason in the chatter."""
        self._check_transition('action_hold')
        vals = {'state': 'on_hold'}
        self.write(vals)
        if reason:
            for order in self:
                order.message_post(body=_("On hold: %s") % reason)

    def action_await_part(self, reason=False):
        """Marks the work order as awaiting parts and optionally logs the reason."""
        self._check_transition('action_await_part')
        self.write({'state': 'awaiting_part'})
        if reason:
            for order in self:
                order.message_post(body=_("Awaiting part: %s") % reason)

    def action_resume(self):
        """Resumes a work order that is on hold or awaiting parts."""
        self._check_transition('action_resume')
        self.write({'state': 'in_progress'})

    def action_done(self):
        """Completes the work order, records completion details, and restores room availability if applicable."""
        self._check_transition('action_done')
        for order in self:
            order.write({'state': 'done'})
            if order.set_ooo and order.space_id and order.space_id.status == 'ooo':
                order.space_id.action_release_ooo()

    def action_cancel(self):
        """Cancels a draft or open work order."""
        terminal = self.filtered(lambda o: o.state in ('done', 'cancelled'))
        if terminal:
            raise UserError(_(
                "Cannot cancel work order(s) %s: already done or "
                "cancelled.") % ', '.join(terminal.mapped('name')))
        self.write({'state': 'cancelled'})