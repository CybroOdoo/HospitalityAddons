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
"""
RATE-02 — hospitality.rate.code + state machine

Core rate-code entity with derivation, validity, market segment tagging,
default policies, and state transitions.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date


class HospitalityRateCode(models.Model):
    _name = 'hospitality.rate.code'
    _description = 'Hospitality Rate Code'
    _inherit = ['mail.thread', 'hospitality.mixin.property']
    _order = 'property_id, code'

    # ═══════════════════════════════════════════════════════════════════════
    # FIELDS
    # ═══════════════════════════════════════════════════════════════════════

    name = fields.Char(
        string='Rate Name',
        required=True,
        translate=True,
        tracking=True,
    )

    code = fields.Char(
        string='Rate Code',
        size=16,
        required=True,
        index=True,
        tracking=True,
    )

    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=False,  # nullable for global rates
        ondelete='restrict',
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True,
    )

    type = fields.Selection(
        selection=[
            ('public', 'Public'),
            ('corporate', 'Corporate'),
            ('package', 'Package'),
            ('group', 'Group'),
            ('complimentary', 'Complimentary'),
            ('house_use', 'House Use'),
            ('day_use', 'Day Use'),
        ],
        string='Rate Type',
        required=True,
        default='public',
        tracking=True,
    )

    # ── Derivation ─────────────────────────────────────────────────────────

    base_rate_code_id = fields.Many2one(
        comodel_name='hospitality.rate.code',
        string='Base Rate Code',
        ondelete='restrict',
        domain="[('derive_method', '=', 'none')]",
        help='Parent rate from which this rate derives its pricing.',
        tracking=True,
    )

    derive_method = fields.Selection(
        selection=[
            ('none', 'None (Master Rate)'),
            ('percent', 'Percentage Adjustment'),
            ('fixed_off', 'Fixed Amount Off'),
            ('fixed_on', 'Fixed Amount On'),
        ],
        string='Derivation Method',
        required=True,
        default='none',
        tracking=True,
    )

    derive_value = fields.Float(
        string='Derivation Value',
        digits=(16, 2),
        help='Percentage or fixed amount used in derivation.',
    )

    # ── Package ────────────────────────────────────────────────────────────

    package_id = fields.Many2one(
        comodel_name='hospitality.package',
        string='Package',
        ondelete='set null',
        help='Associated package for package-type rates.',
    )

    # ── Validity ───────────────────────────────────────────────────────────

    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
    )

    start_date = fields.Date(
        string='Start Date',
        tracking=True,
    )

    end_date = fields.Date(
        string='End Date',
        tracking=True,
    )

    # ── Market & Source ────────────────────────────────────────────────────

    market_segment_id = fields.Many2one(
        comodel_name='hospitality.market.segment',
        string='Market Segment',
        ondelete='restrict',
    )

    source_code_id = fields.Many2one(
        comodel_name='hospitality.source.code',
        string='Source Code',
        ondelete='restrict',
    )

    # ── Policies ───────────────────────────────────────────────────────────

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

    # ── Restrictions ───────────────────────────────────────────────────────

    group_only = fields.Boolean(
        string='Group Only',
        default=False,
        help='If checked, this rate is only available for group bookings.',
    )

    # ── Channels (stub for Phase 2) ────────────────────────────────────────

    channel_ids = fields.Many2many(
        comodel_name='hospitality.channel',
        relation='rate_code_channel_rel',
        column1='rate_code_id',
        column2='channel_id',
        string='Distribution Channels',
    )

    # ── Notes ──────────────────────────────────────────────────────────────

    notes = fields.Html(
        string='Internal Notes',
    )

    # ── State Machine ──────────────────────────────────────────────────────

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('inactive', 'Inactive'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
    )

    # ── Related One2many (stubs for future tasks) ──────────────────────────

    plan_ids = fields.One2many(
        comodel_name='hospitality.rate.plan',
        inverse_name='rate_code_id',
        string='Rate Plans',
    )

    restriction_ids = fields.One2many(
        comodel_name='hospitality.rate.restriction',
        inverse_name='rate_code_id',
        string='Restrictions',
    )

    audit_ids = fields.One2many(
        comodel_name='hospitality.rate.audit',
        inverse_name='rate_code_id',
        string='Audit Log',
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ═══════════════════════════════════════════════════════════════════════

    _code_property_company_unique = models.Constraint(
        'UNIQUE(code, property_id, company_id)',
        'Rate code must be unique per property and company.',
    )

    @api.constrains('derive_method', 'base_rate_code_id', 'derive_value')
    def _check_derive_fields(self):
        """
        If derive_method != none:
          - base_rate_code_id must be set
          - derive_value must be set
          - if derive_method == percent, value must be within [-100, 100]
        """
        for record in self:
            if record.derive_method != 'none':
                if not record.base_rate_code_id:
                    raise ValidationError(_(
                        "Rate code '%s': Derivation method '%s' requires a Base Rate Code."
                    ) % (record.code, record.derive_method))

                if record.derive_value == 0.0:
                    raise ValidationError(_(
                        "Rate code '%s': Derivation method '%s' requires a non-zero Derivation Value."
                    ) % (record.code, record.derive_method))

                if record.derive_method == 'percent':
                    if not (-100 <= record.derive_value <= 100):
                        raise ValidationError(_(
                            "Rate code '%s': Percentage derivation value must be between -100 and 100."
                        ) % record.code)

    @api.constrains('base_rate_code_id')
    def _check_derive_depth(self):
        """
        Derivation depth must be ≤ 1.
        A derived rate cannot itself be derived from another derived rate.
        """
        for record in self:
            if record.base_rate_code_id:
                if record.base_rate_code_id.derive_method != 'none':
                    raise ValidationError(_(
                        "Rate code '%s': Cannot derive from another derived rate '%s'. "
                        "Maximum derivation depth is 1 level."
                    ) % (record.code, record.base_rate_code_id.code))

    @api.constrains('start_date', 'end_date')
    def _check_date_validity(self):
        """End date must be >= start date when both are set."""
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date < record.start_date:
                    raise ValidationError(_(
                        "Rate code '%s': End date cannot be earlier than start date."
                    ) % record.code)

    # ═══════════════════════════════════════════════════════════════════════
    # METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def action_activate(self):
        """Transition from draft → active."""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_(
                    "Rate code '%s' can only be activated from Draft state."
                ) % record.code)
            record.state = 'active'

    def action_deactivate(self):
        """Transition from active → inactive."""
        for record in self:
            if record.state != 'active':
                raise ValidationError(_(
                    "Rate code '%s' can only be deactivated from Active state."
                ) % record.code)
            record.state = 'inactive'

    @api.model
    def _cron_expire_rate_codes(self):
        """
        Daily cron job to expire rate codes.
        Active rates with end_date < today → expired.
        """
        today = date.today()
        rates_to_expire = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today),
        ])
        if rates_to_expire:
            rates_to_expire.write({'state': 'expired'})
        return True

    def _apply_derive(self, price):
        """
        Apply derivation logic to a base price.

        :param price: float, base price
        :return: float, derived price
        """
        self.ensure_one()

        if self.derive_method == 'none':
            return price

        if self.derive_method == 'percent':
            # percentage adjustment: price * (1 + derive_value / 100)
            return round(price * (1 + self.derive_value / 100.0), 2)

        elif self.derive_method == 'fixed_off':
            # fixed amount off: price - derive_value
            return round(max(0.0, price - self.derive_value), 2)

        elif self.derive_method == 'fixed_on':
            # fixed amount on: price + derive_value
            return round(price + self.derive_value, 2)

        return price

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTE / ONCHANGE (if needed in future tasks)
    # ═══════════════════════════════════════════════════════════════════════