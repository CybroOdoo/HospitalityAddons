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
from odoo.exceptions import AccessError, UserError


class HospitalityCashierShift(models.Model):
    """Lifecycle of a single cashier's shift: opening drawer count,
    payments taken during the shift, witnessed drops, closing drawer
    count, and the resulting variance.

    NOTE ON STATE MACHINE: the CASH-02 spec's field list defines the
    `state` selection as strictly [open, closed, audited] with a
    default of 'open', while the method list describes
    action_open_shift as a 'draft -> open' transition. There is no
    'draft' value in the selection as specified, so a shift is 'open'
    from the moment it is created. action_open_shift is implemented
    below as an idempotent confirmation/guard rather than a real
    state transition. Flag this to the product owner if a genuine
    draft stage is actually wanted before CASH-03.
    """
    _name = 'hospitality.cashier.shift'
    _inherit = ['mail.thread']
    _description = 'Hospitality Cashier Shift'
    _order = 'started_at desc'

    name = fields.Char(
        string='Shift Reference', readonly=True, copy=False,
        default=lambda self: _('New'),
        help="Unique reference/sequence number for this cashier shift. "
             "Automatically generated from the 'hospitality.cashier.shift' "
             "sequence.",
    )
    user_id = fields.Many2one(
        'res.users', string='Cashier', required=True, tracking=True,
        default=lambda self: self.env.user,
        help="The cashier/user operating this shift. Tracks who is "
             "responsible for cash transactions during the shift period.",
    )
    property_id = fields.Many2one(
        'hospitality.property', string='Property', required=True,
        tracking=True,
        help="The hospitality property where this cashier shift is operating.",
    )
    started_at = fields.Datetime(
        string='Started At', required=True, default=fields.Datetime.now,
        help="Timestamp when the cashier shift began. Defaults to the "
             "current time when the shift is created.",
    )
    ended_at = fields.Datetime(string='Ended At',
                               help="Timestamp when the cashier shift was closed. Set when the "
                                    "shift is closed via action_close_shift().",
                               )
    state = fields.Selection(
        [('open', 'Open'), ('closed', 'Closed'), ('audited', 'Audited')],
        string='Status', required=True, default='open', tracking=True,
        help="Current state of the shift: Open (actively taking payments), "
             "Closed (ready for audit), or Audited (verified and locked).",
    )
    opening_amount_ids = fields.One2many(
        'hospitality.cashier.amount', 'shift_id', string='Opening Amounts',
        domain=[('kind', '=', 'opening')], context={'default_kind': 'opening'},
        help="Cash drawer counts recorded at the start of the shift. "
             "One line per currency in the drawer.",
    )
    closing_amount_ids = fields.One2many(
        'hospitality.cashier.amount', 'shift_id', string='Closing Amounts',
        domain=[('kind', '=', 'closing')], context={'default_kind': 'closing'},
        help="Cash drawer counts recorded at the end of the shift. "
             "One line per currency in the drawer.",
    )
    drop_ids = fields.One2many(
        'hospitality.cashier.drop', 'shift_id', string='Drops',
        help="Cash drops performed during the shift where cash was "
             "removed from the drawer and transferred to a secure location.",
    )
    notes = fields.Text(string='Notes',
                        help="Additional notes about the shift, such as special "
                             "circumstances, exceptions, or comments for the supervisor.",
                        )
    currency_id = fields.Many2one(
        'res.currency', string='Reporting Currency',
        compute='_compute_currency_id', store=True, readonly=True,
        help="The reporting currency used for all reconciliation and "
             "variance calculations. Uses the company's currency.",
    )

    expected_total = fields.Monetary(
        string='Expected Total', compute='_compute_expected_total',
        store=True, currency_field='currency_id',
        help="Net posted payments (credits) recorded by this cashier "
             "during the shift window, converted to the reporting "
             "currency.")
    variance = fields.Monetary(
        string='Variance', compute='_compute_variance', store=True,
        currency_field='currency_id',
        help="Full drawer reconciliation: closing total minus "
             "(opening total + expected payments received - witnessed "
             "drops), in the reporting currency. Positive = overage, "
             "negative = shortage.")

    @api.depends('property_id')
    def _compute_currency_id(self):
        """Set the reporting currency for the shift.

        Uses the company currency for all reconciliation and variance
        calculations.
        """
        for shift in self:
            shift.currency_id = self.env.company.currency_id

    @api.depends('started_at', 'ended_at', 'user_id', 'property_id',
                 'state', 'currency_id')
    def _compute_expected_total(self):
        """Compute the total payments processed by the cashier during the
        shift.

        Searches folio payment transactions within the shift period and
        converts them into the reporting currency.
        """
        try:
            folio_line = self.env['hospitality.folio.line'].sudo()
        except KeyError:
            folio_line = None
        required_fields = {'transaction_type', 'is_void', 'amount_total',
                            'currency_id'}
        schema_ok = (
            folio_line is not None
            and required_fields.issubset(folio_line._fields.keys())
        )
        company = self.env.company
        for shift in self:
            target_currency = shift.currency_id or company.currency_id
            total = 0.0
            if schema_ok and shift.user_id and shift.started_at:
                end = shift.ended_at or fields.Datetime.now()
                domain = [
                    ('transaction_type', '=', 'payment'),
                    ('is_void', '=', False),
                    ('create_uid', '=', shift.user_id.id),
                    ('create_date', '>=', shift.started_at),
                    ('create_date', '<=', end),
                ]
                for line in folio_line.search(domain):
                    amount = -line.amount_total
                    line_currency = line.currency_id or target_currency
                    if line_currency != target_currency:
                        amount = line_currency._convert(
                            amount, target_currency, company,
                            line.create_date or fields.Date.context_today(shift))
                    total += amount
            shift.expected_total = total

    def _currency_line_total(self, lines, target_currency, company):
        """Sum a recordset of lines exposing amount/currency_id fields,
        converting each to target_currency."""
        total = 0.0
        for line in lines:
            amount = line.amount
            line_currency = line.currency_id or target_currency
            if line_currency != target_currency:
                amount = line_currency._convert(
                    amount, target_currency, company,
                    fields.Date.context_today(self))
            total += amount
        return total

    @api.depends('opening_amount_ids.amount', 'opening_amount_ids.currency_id',
                 'closing_amount_ids.amount', 'closing_amount_ids.currency_id',
                 'drop_ids.amount', 'drop_ids.currency_id',
                 'expected_total', 'currency_id')
    def _compute_variance(self):
        """Compute the drawer variance for the shift.

        Variance is calculated as the difference between the counted closing
        cash and the expected closing balance after payments and cash drops.
        """
        company = self.env.company
        for shift in self:
            target_currency = shift.currency_id or company.currency_id
            opening_total = shift._currency_line_total(
                shift.opening_amount_ids, target_currency, company)
            closing_total = shift._currency_line_total(
                shift.closing_amount_ids, target_currency, company)
            drops_total = shift._currency_line_total(
                shift.drop_ids, target_currency, company)
            expected_closing = (
                opening_total + shift.expected_total - drops_total)
            shift.variance = closing_total - expected_closing

    @api.model_create_multi
    def create(self, vals_list):
        """Assign a sequence-generated reference when creating a cashier
        shift."""
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code(
                        'hospitality.cashier.shift') or _('New'))
        return super().create(vals_list)

    @api.model
    def _get_or_create_open_shift(self, user=None, property_id=None):
        """Helper for future payment-posting flows (CASH-03+): return
        the current open shift for a cashier/property, auto-creating
        one if none exists yet."""
        user = user or self.env.user
        domain = [('user_id', '=', user.id), ('state', '=', 'open')]
        if property_id:
            domain.append(('property_id', '=', int(property_id)))
        shift = self.search(domain, limit=1)
        if not shift:
            vals = {'user_id': user.id}
            if property_id:
                vals['property_id'] = int(property_id)
            shift = self.create(vals)
        return shift

    def action_open_shift(self):
        """Idempotent confirmation that the shift is open. See the
        class docstring for why this doesn't perform a draft->open
        transition as originally described.

        Clears ended_at when transitioning into 'open' - a stale
        ended_at left over from a prior close would otherwise silently
        truncate the window _compute_expected_total searches, even
        though the shift is open again."""
        for shift in self:
            if shift.state == 'closed':
                raise UserError(_(
                    "A closed shift cannot be reopened directly. "
                    "Contact a supervisor."))
            if shift.state == 'audited':
                raise UserError(_(
                    "An audited shift is locked and cannot be reopened."))
            shift.write({'state': 'open', 'ended_at': False})
        return True

    def action_close_shift(self):
        """Close the cashier shift after validating the closing drawer
        amounts.

        Records the closing time and updates the shift status.
        """
        for shift in self:
            if shift.state != 'open':
                raise UserError(_("Only an open shift can be closed."))
            if not shift.closing_amount_ids:
                raise UserError(_(
                    "Please capture the closing drawer amounts before "
                    "closing the shift."))
            shift.write({
                'ended_at': fields.Datetime.now(),
                'state': 'closed',
            })
        return True

    def action_audit(self):
        """Mark a closed cashier shift as audited.

        Only users with Cashier Supervisor privileges can perform this
        operation.
        """
        if not self.env.user.has_group(
                'hospitality_cashiering.group_cashier_supervisor'):
            raise AccessError(_(
                "Only a Cashier Supervisor can audit a shift."))
        for shift in self:
            if shift.state != 'closed':
                raise UserError(_("Only a closed shift can be audited."))
            shift.state = 'audited'
        return True

    def _get_closeout_payment_lines(self):
        """Return the folio payment lines posted by this shift's cashier
        during the shift window (same domain as _compute_expected_total),
        for use by the closeout report."""
        self.ensure_one()
        FolioLine = self.env['hospitality.folio.line'].sudo()
        if 'transaction_type' not in FolioLine._fields:
            return FolioLine
        end = self.ended_at or fields.Datetime.now()
        domain = [
            ('transaction_type', '=', 'payment'),
            ('is_void', '=', False),
            ('create_uid', '=', self.user_id.id),
            ('create_date', '>=', self.started_at),
            ('create_date', '<=', end),
        ]
        return FolioLine.search(domain, order='transaction_code_id, create_date')

    def _get_closeout_payments_by_code(self):
        """Group this shift's payment lines by transaction code, with a
        per-group total (positive 'cash taken in' figure), for the
        closeout report."""
        self.ensure_one()
        lines = self._get_closeout_payment_lines()
        ordered_codes = lines.mapped('transaction_code_id')
        groups = []
        for code in ordered_codes:
            code_lines = lines.filtered(
                lambda l: l.transaction_code_id == code)
            groups.append({
                'transaction_code': code,
                'lines': code_lines,
                'total': -sum(code_lines.mapped('amount_total')),
            })
        return groups

    def action_print_shift_closeout(self):
        """Print the Cashier Shift Closeout PDF for this shift."""
        self.ensure_one()
        return self.env.ref(
            'hospitality_cashiering.action_report_cashier_shift_closeout'
        ).report_action(self)