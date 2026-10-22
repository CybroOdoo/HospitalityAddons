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


class HospitalityBePromoCode(models.Model):
    """Discount code redeemable through the public booking engine.
    Enforces exactly one of a percentage or fixed discount, and a
    hard cap on the number of times it may be used."""

    _name = 'hospitality.be.promo.code'
    _description = 'Booking Engine Promo Code'
    _rec_name = 'code'
    _order = 'code'

    code = fields.Char(string='Code', size=24, required=True, index=True)
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='property_id.currency_id',
        store=True,
        readonly=True,
    )
    discount_pct = fields.Float(string='Discount %', default=0.0)
    discount_fixed = fields.Monetary(
        string='Discount (Fixed)',
        currency_field='currency_id',
        default=0.0,
    )
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    max_uses = fields.Integer(
        string='Max Uses',
        default=0,
        help='Maximum number of times this code may be redeemed. '
             '0 = unlimited.',
    )
    used_count = fields.Integer(string='Used Count', default=0, readonly=True)
    applies_to_rate_codes = fields.Many2many(
        comodel_name='hospitality.rate.code',
        relation='hospitality_be_promo_code_rate_code_rel',
        column1='promo_code_id',
        column2='rate_code_id',
        string='Applies To Rate Codes',
    )
    active = fields.Boolean(string='Active', default=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'This promo code already exists. Codes must be unique.',
    )

    @api.constrains('discount_pct', 'discount_fixed')
    def _check_discount_xor(self):
        """Ensures that each promo code defines exactly one discount type.
        Validates that either a percentage discount or a fixed monetary
        discount is configured, but never both and never neither.
        Raises a ValidationError if the rule is violated.
        """
        for promo in self:
            has_pct = bool(promo.discount_pct)
            has_fixed = bool(promo.discount_fixed)
            if has_pct == has_fixed:
                raise ValidationError(
                    f"Promo code '{promo.code}': set exactly one of "
                    f"Discount % or Discount (Fixed) — not both, and "
                    f"not neither."
                )

    @api.constrains('used_count', 'max_uses')
    def _check_max_uses(self):
        """Validates that the recorded usage count does not exceed the
        configured maximum number of allowed redemptions.
        A maximum value of 0 indicates unlimited usage and is therefore
        excluded from this validation.
        """
        for promo in self:
            if promo.max_uses > 0 and promo.used_count > promo.max_uses:
                raise ValidationError(
                    f"Promo code '{promo.code}' cannot exceed its "
                    f"maximum allowed uses ({promo.max_uses})."
                )

    def _consume(self):
        """Redeem a single use of this promo code, rejecting the
        redemption once the usage cap has been reached. Intended to be
        called from the booking checkout flow when the code is applied
        to a confirmed reservation."""
        self.ensure_one()
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            raise ValidationError(
                f"Promo code '{self.code}' has reached its usage limit "
                f"and can no longer be applied."
            )
        self.used_count += 1

    @api.model
    def _find_valid_promo(self, code, property_id=None):
        """BE-05: look up an active, currently-valid promo code by its
        code string for the public booking cart. Returns the matching
        record, or an empty recordset if not found, not yet started,
        expired, scoped to a different property, or already at its
        usage cap. Does NOT consume a use — call _consume() separately
        once the booking is actually confirmed and paid."""
        if not code:
            return self.browse()
        promo = self.search([
            ('code', '=ilike', code.strip()),
            ('active', '=', True),
        ], limit=1)
        if not promo:
            return self.browse()
        today = fields.Date.context_today(self)
        if promo.start_date and promo.start_date > today:
            return self.browse()
        if promo.end_date and promo.end_date < today:
            return self.browse()
        if property_id and promo.property_id and promo.property_id.id != property_id:
            return self.browse()
        if promo.max_uses > 0 and promo.used_count >= promo.max_uses:
            return self.browse()
        return promo