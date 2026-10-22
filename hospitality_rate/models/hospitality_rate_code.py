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
from datetime import date, timedelta


class HospitalityRateCode(models.Model):
    """
    Rate Code defining pricing rules for hospitality properties.

    Supports master rates, derived rates (percentage/fixed adjustments),
    validity periods, market segmentation, channel distribution, and
    package bundling. Rates can be global or property-specific.
    """
    _name = 'hospitality.rate.code'
    _description = 'Hospitality Rate Code'
    _inherit = ['mail.thread', 'hospitality.mixin.property']
    _order = 'property_id, code'

    name = fields.Char(
        string='Rate Name',
        required=True,
        translate=True,
        tracking=True,
        help="Display name of the rate (e.g., 'Standard Room Rate', 'Executive Special').",
    )
    code = fields.Char(
        string='Rate Code',
        size=16,
        required=True,
        index=True,
        tracking=True,
        help="Unique alphanumeric identifier for the rate (e.g., 'STD-RM', 'EXEC-01').",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=False,
        ondelete='restrict',
        tracking=True,
        help="Property offering this rate. Leave empty for global rates available across all properties.",
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
        help="Categorization of the rate: public, corporate, package, group, complimentary, house use, or day use.",
    )
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
        help="How this rate is derived from the base rate: None (master), percentage adjustment, fixed amount off, "
             "or fixed amount on.",
    )
    derive_value = fields.Float(
        string='Derivation Value',
        digits=(16, 2),
        help='Percentage or fixed amount used in derivation.',
    )
    package_id = fields.Many2one(
        comodel_name='hospitality.package',
        string='Package',
        ondelete='set null',
        help='Associated package for package-type rates.',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help="Uncheck to archive the rate. Inactive rates are hidden from selection lists.",
    )
    start_date = fields.Date(
        string='Start Date',
        tracking=True,
        help="Date from which this rate becomes valid. Leave empty for no start restriction.",
    )
    end_date = fields.Date(
        string='End Date',
        tracking=True,
        help="Date after which this rate expires. Active rates with end_date < today are auto-expired by cron.",
    )
    market_segment_id = fields.Many2one(
        comodel_name='hospitality.market.segment',
        string='Market Segment',
        ondelete='restrict',
        help="Market segment this rate applies to (e.g., 'Corporate', 'Leisure', 'Group').",
    )
    source_code_id = fields.Many2one(
        comodel_name='hospitality.source.code',
        string='Source Code',
        ondelete='restrict',
        help="Source code this rate is associated with (e.g., 'OTA', 'Direct', 'GDS').",
    )
    cancellation_policy_id = fields.Many2one(
        comodel_name='hospitality.cancellation.policy',
        string='Cancellation Policy',
        ondelete='set null',
        help="Cancellation policy applicable to bookings using this rate.",
    )
    deposit_policy_id = fields.Many2one(
        comodel_name='hospitality.deposit.policy',
        string='Deposit Policy',
        ondelete='set null',
        help="Deposit policy applicable to bookings using this rate.",
    )
    group_only = fields.Boolean(
        string='Group Only',
        default=False,
        help='If checked, this rate is only available for group bookings.',
    )
    channel_ids = fields.Many2many(
        comodel_name='hospitality.channel',
        relation='rate_code_channel_rel',
        column1='rate_code_id',
        column2='channel_id',
        string='Distribution Channels',
        help="Distribution channels through which this rate is available (e.g., Booking.com, Expedia, Direct).",
    )
    notes = fields.Html(
        string='Internal Notes',
        help="Internal notes or comments about this rate. Not visible to customers.",
    )
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
        help="Lifecycle state: Draft → Active → Expired/Inactive. Active rates are available for booking.",
    )
    plan_ids = fields.One2many(
        comodel_name='hospitality.rate.plan',
        inverse_name='rate_code_id',
        string='Rate Plans',
        help="Rate plans defining prices per room type, date ranges, and weekdays.",
    )
    restriction_ids = fields.One2many(
        comodel_name='hospitality.rate.restriction',
        inverse_name='rate_code_id',
        string='Restrictions',
        help="Restrictions applying to this rate (minimum stay, closed to arrival, etc.).",
    )
    audit_ids = fields.One2many(
        comodel_name='hospitality.rate.audit',
        inverse_name='rate_code_id',
        string='Audit Log',
        help="Audit trail of all changes made to this rate.",
    )

    @api.constrains('code', 'property_id')
    def _check_unique_code_per_property_company(self):
        """Ensure rate code is unique per property and company."""
        for record in self:
            duplicate = self.search(
                [('code', '=', record.code), ('id', '!=', record.id),
                 ('property_id', '=', record.property_id.id),
                 ('id', '!=', record.id)], limit=1)
            if duplicate:
                raise ValidationError(
                    "Rate code '%s' must be unique per property. "
                    "This code is already used." % record.code
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
                    raise ValidationError(
                        "Rate code '%s': Derivation method '%s' requires a Base Rate Code."
                     % (record.code, record.derive_method))

                if record.derive_value == 0.0:
                    raise ValidationError(
                        "Rate code '%s': Derivation method '%s' requires a non-zero Derivation Value."
                     % (record.code, record.derive_method))

                if record.derive_method == 'percent':
                    if not (-100 <= record.derive_value <= 100):
                        raise ValidationError(
                            "Rate code '%s': Percentage derivation value must be between -100 and 100."
                         % record.code)

    @api.constrains('base_rate_code_id')
    def _check_derive_depth(self):
        """
        Derivation depth must be ≤ 1.
        A derived rate cannot itself be derived from another derived rate.
        """
        for record in self:
            if record.base_rate_code_id:
                if record.base_rate_code_id.derive_method != 'none':
                    raise ValidationError(
                        "Rate code '%s': Cannot derive from another derived rate '%s'. "
                        "Maximum derivation depth is 1 level."
                     % (record.code, record.base_rate_code_id.code))

    @api.constrains('start_date', 'end_date')
    def _check_date_validity(self):
        """End date must be >= start date when both are set."""
        for record in self:
            if record.start_date and record.end_date:
                if record.end_date < record.start_date:
                    raise ValidationError(
                        "Rate code '%s': End date cannot be earlier than start date."
                     % record.code)

    def action_activate(self):
        """Transition from draft → active."""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(
                    "Rate code '%s' can only be activated from Draft state."
                 % record.code)
            record.state = 'active'

    def action_deactivate(self):
        """Transition from active → inactive."""
        for record in self:
            if record.state != 'active':
                raise ValidationError(
                    "Rate code '%s' can only be deactivated from Active state."
                 % record.code)
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
            return price * (1 + self.derive_value / 100.0)
        elif self.derive_method == 'fixed_off':
            return max(0.0, price - self.derive_value)
        elif self.derive_method == 'fixed_on':
            return price + self.derive_value
        return price

    def _get_rate(self, property_id, space_type_id, rate_code_id,
                  arrival, departure, occupancy):
        """
        Single pricing call used by booking engine, front desk,
        channel managers, and reports.

        :param property_id: int, id of hospitality.property.
        :param space_type_id: int, id of hospitality.space.type.
        :param rate_code_id: int, id of hospitality.rate.code.
        :param arrival: date, inclusive arrival date.
        :param departure: date, exclusive departure date.
        :param occupancy: dict with keys 'adults' (int) and 'children' (int).
        :return: dict with keys:
            - nightly: list of (date, amount) tuples; amount may be None.
            - inclusions: list of dicts {transaction_code_id, qty, value, when}.
            - restrictions: list of violation code strings.
            - currency_id: int, id of the currency.
        :raises ValidationError: on invalid inputs.
        """
        self.ensure_one()
        if not arrival or not departure:
            raise ValidationError(
                "Arrival and departure dates are required."
            )
        if departure <= arrival:
            raise ValidationError(
                "Departure must be after arrival."
            )
        adults = occupancy.get('adults', 0) if occupancy else 0
        if not isinstance(adults, int) or adults < 1:
            raise ValidationError(
                "Occupancy must contain a positive integer 'adults'."
            )
        children = occupancy.get('children', 0) if occupancy else 0
        is_derived = self.derive_method != 'none'
        base_rate = self.base_rate_code_id if is_derived else self
        Restriction = self.env['hospitality.rate.restriction']
        violations = Restriction._evaluate(
            rate_code_id, space_type_id, arrival, departure
        )
        all_plans = self.env['hospitality.rate.plan'].search([
            ('rate_code_id', '=', base_rate.id),
            ('space_type_id', '=', space_type_id),
            ('date_from', '<=', (departure - timedelta(days=1)).strftime('%Y-%m-%d')),
            ('date_to', '>=', arrival.strftime('%Y-%m-%d')),
        ])
        _plan_cache = {}

        def _plan_for_date(d):
            if d in _plan_cache:
                return _plan_cache[d]
            plan = None
            for p in all_plans:
                if p.date_from <= d <= p.date_to:
                    weekday_bit = d.weekday()
                    if p.weekday_mask & (1 << weekday_bit):
                        plan = p
                        break
            _plan_cache[d] = plan
            return plan

        nightly = []
        current = arrival
        while current < departure:
            plan = _plan_for_date(current)
            if plan is None:
                price = None
            else:
                price = plan._price_for_night(current, adults, children)
                if price is not None and is_derived:
                    price = self._apply_derive(price)
            nightly.append((current, price))
            current += timedelta(days=1)
        inclusions = []
        if self.package_id:
            for incl in self.package_id.inclusion_ids:
                rows = _expand_inclusion(incl, arrival, departure, occupancy)
                inclusions.extend(rows)
        if all_plans:
            currency_id = all_plans[0].currency_id.id
        else:
            currency_id = self.env.company.currency_id.id
        return {
            'nightly': nightly,
            'inclusions': inclusions,
            'restrictions': violations,
            'currency_id': currency_id,
        }


def _expand_inclusion(inclusion, arrival, departure, occupancy):
    """
    Expand a single hospitality.package.inclusion into a list of posting rows.

    :param inclusion: hospitality.package.inclusion record.
    :param arrival: date, inclusive arrival.
    :param departure: date, exclusive departure.
    :param occupancy: dict with 'adults' and 'children'.
    :return: list of dicts {transaction_code_id, qty, value, when}.
    """
    tc_id = inclusion.transaction_code_id.id
    qty = inclusion.qty
    value = inclusion.value
    rhythm = inclusion.posting_rhythm
    adults = occupancy.get('adults', 1)
    children = occupancy.get('children', 0)
    pax = adults + children
    rows = []
    if rhythm == 'per_stay':
        rows.append({
            'transaction_code_id': tc_id,
            'qty': qty,
            'value': value,
            'when': arrival,
        })
    elif rhythm == 'per_night':
        current = arrival
        while current < departure:
            rows.append({
                'transaction_code_id': tc_id,
                'qty': qty,
                'value': value,
                'when': current,
            })
            current += timedelta(days=1)
    elif rhythm == 'per_pax_per_night':
        current = arrival
        while current < departure:
            for _ in range(pax):
                rows.append({
                    'transaction_code_id': tc_id,
                    'qty': qty,
                    'value': value,
                    'when': current,
                })
            current += timedelta(days=1)
    elif rhythm == 'on_arrival':
        rows.append({
            'transaction_code_id': tc_id,
            'qty': qty,
            'value': value,
            'when': 'on_arrival',
        })
    return rows
