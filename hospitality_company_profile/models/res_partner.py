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
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    """Extend partners with hospitality corporate and commission management."""
    _inherit = 'res.partner'

    is_corporate_account = fields.Boolean(
        string='Corporate Account',
        default=False,
        index=True,
        help='Indicates whether the partner is a corporate account.',
    )
    is_travel_agent = fields.Boolean(
        string='Travel Agent',
        default=False,
        index=True,
        help='Indicates whether the partner is a travel agent.',
    )
    is_ota = fields.Boolean(
        string='OTA',
        default=False,
        index=True,
        help='Indicates whether the partner is an online travel agency.',
    )
    iata_number = fields.Char(
        string='IATA Number',
        size=16,
        help='IATA identification number of the travel agent.',
    )
    commission_method = fields.Selection(
        selection=[
            ('pct_room',         'Percentage of Room Rate'),
            ('pct_total',        'Percentage of Total Folio'),
            ('fixed_per_stay',   'Fixed Amount per Stay'),
            ('tiered_by_volume', 'Tiered by Volume'),
        ],
        string='Commission Method',
        help='Method used to calculate the partner commission.',
    )
    commission_pct = fields.Float(
        string='Commission % / Fixed Amount',
        digits=(10, 4),
        help='Percentage (0-100) or fixed monetary amount depending on Commission Method.',
    )
    commission_tier_ids = fields.One2many(
        comodel_name='hospitality.commission.tier',
        inverse_name='partner_id',
        string='Commission Tiers',
        help='Volume-based commission tiers configured for the partner.',
    )
    payment_terms_id = fields.Many2one(
        comodel_name='account.payment.term',
        string='Payment Terms',
        ondelete='set null',
        help='Payment terms applicable to the partner.',
    )
    account_manager_id = fields.Many2one(
        comodel_name='res.users',
        string='Account Manager',
        ondelete='set null',
        domain=[('share', '=', False)],
        help='Internal user responsible for managing this partner account.',
    )
    hospitality_credit_limit = fields.Monetary(
        string='Hospitality Credit Limit',
        currency_field='currency_id',
        default=0.0,
        groups='hospitality_company_profile.group_corporate_finance',
        help='Maximum credit amount allowed for hospitality transactions.',
    )
    credit_used = fields.Monetary(
        string='Credit Used',
        currency_field='currency_id',
        compute='_compute_credit_used',
        store=True,
        help='Outstanding amount currently used from the hospitality credit limit.',
    )
    credit_hold_manual = fields.Boolean(
        string='Manual Credit Hold',
        default=False,
        groups='hospitality_company_profile.group_corporate_finance',
        help='Indicates whether the partner is manually placed on credit hold.',
    )
    credit_status = fields.Selection(
        selection=[
            ('ok',         'OK'),
            ('near_limit', 'Near Limit'),
            ('exceeded',   'Exceeded'),
            ('on_hold',    'On Hold'),
        ],
        string='Credit Status',
        compute='_compute_credit_status',
        store=True,
        help='Current credit status based on credit usage and hold settings.',
    )

    @api.depends(
        'is_corporate_account',
        'is_travel_agent',
        'is_ota',
        'invoice_ids.amount_residual',
        'invoice_ids.payment_state',
        'invoice_ids.state',
        'invoice_ids.move_type',
    )
    def _compute_credit_used(self):
        """Sum amount_residual on open customer invoices for this partner.

        NOTE: This field is `store=True` but its true data source
        (account.move.amount_residual) cannot be expressed as an ORM
        dependency. The @api.depends above only covers in-app triggers
        (e.g. toggling the corporate flag). The authoritative refresh
        path is the daily `cron_credit_recompute` (see
        _cron_credit_recompute), which explicitly invalidates and
        recomputes this field for all corporate/TA/OTA partners.
        """
        AccountMove = self.env['account.move']
        for rec in self:
            moves = AccountMove.search([
                ('partner_id', '=', rec.id),
                ('move_type', '=', 'out_invoice'),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('state', '=', 'posted'),
            ])
            rec.credit_used = sum(moves.mapped('amount_residual'))

    @api.depends('credit_hold_manual', 'hospitality_credit_limit', 'credit_used')
    def _compute_credit_status(self):
        """Compute the partner's current hospitality credit status."""
        for rec in self:
            if rec.credit_hold_manual:
                rec.credit_status = 'on_hold'
            elif not rec.hospitality_credit_limit:
                rec.credit_status = 'ok'
            elif rec.credit_used > rec.hospitality_credit_limit:
                rec.credit_status = 'exceeded'
            elif rec.credit_used > 0.8 * rec.hospitality_credit_limit:
                rec.credit_status = 'near_limit'
            else:
                rec.credit_status = 'ok'

    is_any_corporate = fields.Boolean(
        string='Has Corporate/TA/OTA Flag',
        compute='_compute_is_any_corporate',
        store=False,
        help='Indicates whether the partner is a corporate account, travel agent, or OTA.',
    )

    @api.depends('is_corporate_account', 'is_travel_agent', 'is_ota')
    def _compute_is_any_corporate(self):
        """Compute whether any corporate partner flag is enabled."""
        for rec in self:
            rec.is_any_corporate = (
                rec.is_corporate_account or rec.is_travel_agent or rec.is_ota
            )

    @api.constrains('is_corporate_account', 'is_travel_agent', 'is_ota')
    def _check_not_guest_and_corporate(self):
        """Prevent a guest from having corporate, TA, or OTA flags."""
        for rec in self:
            guest_flag = getattr(rec, 'is_guest', False)
            if guest_flag and (
                rec.is_corporate_account or rec.is_travel_agent or rec.is_ota
            ):
                raise ValidationError(
                    "Partner '%s' is marked as a Guest and cannot simultaneously "
                    "hold a Corporate, Travel Agent or OTA flag. "
                    "Please remove the conflicting flag before saving." % rec.name
                )

    @api.constrains('is_travel_agent', 'iata_number')
    def _check_ta_requires_iata(self):
        """Ensure travel agents have an IATA number."""
        for rec in self:
            if rec.is_travel_agent and not (rec.iata_number or '').strip():
                raise ValidationError(
                    "Partner '%s' is marked as a Travel Agent but has no IATA Number. "
                    "Please provide the IATA Number before saving." % rec.name
                )

    def compute_commission(self, room_revenue, total_revenue, room_nights):
        """Return the commission amount for this partner.

        Args:
            room_revenue  (float): revenue from room charges only.
            total_revenue (float): total folio revenue.
            room_nights   (int/float): number of room-nights in the stay.

        Returns:
            float: commission amount in the partner's currency.
        """
        self.ensure_one()
        method = self.commission_method
        pct = self.commission_pct
        if method == 'pct_room':
            return round(pct / 100.0 * room_revenue, 2)
        if method == 'pct_total':
            return round(pct / 100.0 * total_revenue, 2)
        if method == 'fixed_per_stay':
            return round(pct, 2)
        if method == 'tiered_by_volume':
            return self._compute_tiered_commission(room_nights, total_revenue)
        return 0.0

    def _compute_tiered_commission(self, room_nights, total_revenue):
        """Look up the matching tier and apply it to the appropriate basis value."""
        self.ensure_one()
        for basis, value in (('revenue', total_revenue), ('nights', room_nights)):
            tiers = self.commission_tier_ids.filtered(
                lambda t: t.volume_basis == basis
            ).sorted(key=lambda t: t.lower_volume)
            for tier in tiers:
                upper = tier.upper_volume if tier.upper_volume else float('inf')
                if tier.lower_volume <= value < upper:
                    return round(tier.commission_pct / 100.0 * total_revenue, 2)
        return 0.0

    @api.model
    def _cron_credit_recompute(self):
        """Daily cron: refresh credit_used / credit_status for corporate/TA/OTA partners.

        Invalidates the cache for the computed fields so the next read
        re-triggers _compute_credit_used / _compute_credit_status with
        fresh data from account.move.
        """
        partners = self.search([
            '|', '|',
            ('is_corporate_account', '=', True),
            ('is_travel_agent', '=', True),
            ('is_ota', '=', True),
        ])
        if not partners:
            return
        partners.invalidate_recordset(['credit_used', 'credit_status'])
        partners._compute_credit_used()
        partners._compute_credit_status()
