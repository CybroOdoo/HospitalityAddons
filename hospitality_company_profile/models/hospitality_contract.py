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
from odoo.exceptions import UserError, ValidationError

class HospitalityContract(models.Model):
    """Manage partner contracts and their validity and lifecycle."""
    _name = 'hospitality.contract'
    _description = 'Hospitality Contract'
    _inherit = ['mail.thread']
    _order = 'partner_id, start_date desc'

    name = fields.Char(
        string='Contract Name',
        required=True,
        help='Name used to identify the contract.',
    )
    code = fields.Char(
        string='Contract Code',
        size=24,
        required=True,
        index=True,
        copy=False,
        help='Unique contract code for the partner.',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        required=True,
        index=True,
        ondelete='restrict',
        help='Partner associated with this contract.',
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        ondelete='set null',
        help='Leave blank to apply contract to all properties.',
    )
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='Date from which the contract becomes valid.',
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Date until which the contract remains valid.',
    )

    # ─── Rates & policies ─────────────────────────────────────────────────────

    # NOTE: rate_code_ids (Many2many → hospitality.rate.code) is intentionally
    # deferred until RATE-02 lands and that model is available in the registry.
    # Declaring the field before the comodel exists causes an AssertionError
    # during ORM setup in Odoo 19.
    # rate_code_ids = fields.Many2many(
    #     comodel_name='hospitality.rate.code',
    #     string='Rate Codes',
    # )

    discount_pct = fields.Float(
        string='Discount %',
        digits=(10, 4),
        help='Discount percentage provided under the contract.',
    )
    allowance_room_nights = fields.Integer(
        string='Allowance (Room Nights)',
        help='Number of room nights included in the contract allowance.',
    )
    cancellation_policy_id = fields.Many2one(
        comodel_name='hospitality.cancellation.policy',
        string='Cancellation Policy',
        ondelete='set null',
    )
    deposit_policy_id = fields.Many2one(
        comodel_name='hospitality.deposit.policy',
        string='Deposit Policy',
        ondelete='set null',
    )
    state = fields.Selection(
        selection=[
            ('draft',      'Draft'),
            ('active',     'Active'),
            ('expired',    'Expired'),
            ('terminated', 'Terminated'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        help='Current lifecycle status of the contract.',
    )
    document_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='Contract Document',
        ondelete='set null',
        help='Document attached to the contract.',
    )
    notes = fields.Html(
        string='Notes',
        help='Additional notes or terms related to the contract.',
    )
    termination_reason = fields.Text(
        string='Termination Reason',
        readonly=True,
        help='Reason provided for terminating the contract.',
    )
    terminated_by = fields.Many2one(
        comodel_name='res.users',
        string='Terminated By',
        readonly=True,
        ondelete='set null',
        help='User who terminated the contract.',
    )
    terminated_at = fields.Datetime(
        string='Terminated At',
        readonly=True,
        help='Date and time when the contract was terminated.',
    )

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Ensure the contract end date is not before its start date."""
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError(
                    "Contract '%s': End Date must be on or after Start Date." % rec.name
                )

    @api.constrains('code', 'partner_id')
    def _check_code_unique(self):
        """Ensure the contract code is unique for each partner."""
        for rec in self:
            if not rec.code or not rec.partner_id:
                continue
            duplicate = self.search([
                ('code', '=', rec.code),
                ('partner_id', '=', rec.partner_id.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Contract code '%s' must be unique for partner '%s'."
                    % (rec.code, rec.partner_id.name)
                )

    def action_activate(self):
        """Transition draft → active. Guard: state must be draft."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    "Only contracts in Draft state can be activated. "
                    "'%s' is currently '%s'." % (rec.name, rec.state)
                )
            rec.state = 'active'

    def action_terminate(self):
        """Open the termination wizard. Guard: state must be active."""
        self.ensure_one()
        if self.state != 'active':
            raise UserError(
                "Only active contracts can be terminated. "
                "'%s' is currently '%s'." % (self.name, self.state)
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Terminate Contract',
            'res_model': 'hospitality.contract.terminate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_contract_id': self.id},
        }

    @api.model
    def _cron_expire_contracts(self):
        """Daily cron: flip active contracts past their end_date to expired."""
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today),
        ])
        if expired:
            expired.write({'state': 'expired'})
