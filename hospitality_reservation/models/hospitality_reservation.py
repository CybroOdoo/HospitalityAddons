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
import uuid
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class HospitalityReservation(models.Model):
    """
    Core reservation management for hotel properties.

    This model serves as the central hub for all reservation-related operations in the
    hospitality system. It manages the complete lifecycle of a booking from creation
    through check-out, including guest information, stay details, rate management,
    deposit tracking, and cancellation handling.
    """
    _name = 'hospitality.reservation'
    _description = 'Hospitality Reservation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'hospitality.mixin.property']
    _order = 'arrival desc, id desc'

    # ── Identification ────────────────────────────────────────────────────────

    name = fields.Char(
        string='Reservation No.',
        readonly=True,
        copy=False,
        default='/',
        help='Unique reservation number. Auto-generated from property sequence.',
    )
    property_id = fields.Many2one(
        'hospitality.property',
        string='Property',
        required=True,
        index=True,
        tracking=True,
        help='Hotel property for this reservation. Determines available rooms and rates.',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('option', 'Option / Hold'),
            ('confirmed', 'Confirmed'),
            ('checked_in', 'Checked In'),
            ('checked_out', 'Checked Out'),
            ('no_show', 'No Show'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        copy=False,
        help="Reservation Status",
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Guest',
        required=True,
        index=True,
        tracking=True,
        help='Primary guest responsible for the booking. Sources VIP level and preferences.',
    )
    contact_partner_id = fields.Many2one(
        'res.partner',
        string='Booker / Contact',
        help='Booker if different from the travelling guest.',
    )
    company_partner_id = fields.Many2one(
        'res.partner',
        string='Account (Corporate / TA / OTA)',
        domain=[
            '|', '|',
            ('is_corporate_account', '=', True),
            ('is_travel_agent', '=', True),
            ('is_ota', '=', True),
        ],
        help='Billing account: Corporate, Travel Agent, or OTA for direct billing/reporting.',
    )
    arrival = fields.Date(
        string='Arrival',
        required=True,
        index=True,
        tracking=True,
        help='Expected check-in date. Must be before departure.',
    )
    departure = fields.Date(
        string='Departure',
        required=True,
        index=True,
        tracking=True,
        help='Expected check-out date. Must be after arrival.',
    )
    arrival_time = fields.Float(
        string='Arrival Time',
        default=lambda self: self._default_arrival_time(),
        help='Expected arrival time (24 h float, e.g. 14.0 = 14:00).',
    )
    nights = fields.Integer(
        string='Nights',
        compute='_compute_nights',
        store=True,
        help='Total nights = departure - arrival. Stored for performance.',
    )
    adults = fields.Integer(string='Adults', required=True, default=2,
                            help='Number of adult guests (18+). Minimum 1. Affects rate calculations.', )
    children = fields.Integer(string='Children', default=0,
                              help='Number of child guests (3-17). Affects occupancy limits.', )
    infants = fields.Integer(string='Infants', default=0,
                             help='Number of infants (0-2). Tracked for occupancy limits only.', )
    child_ages = fields.Char(
        string='Child Ages',
        help='Comma-separated list of child ages, e.g. "3,7,10".',
    )
    space_type_id = fields.Many2one(
        'hospitality.space.type',
        string='Room Type',
        required=True,
        domain="['|', ('property_id', '=', False), ('property_id', '=', property_id)]",
        help='Booked room type/category. Determines available rooms and rates.',
    )
    space_id = fields.Many2one(
        'hospitality.space',
        string='Room',
        domain="[('property_id','=',property_id),"
               " ('space_type_id','=',space_type_id)]",
        help='Specific room assigned. Must match the room type.',
    )
    rate_code_id = fields.Many2one(
        'hospitality.rate.code',
        string='Rate Code',
        required=True,
        domain="['|', ('property_id', '=', False), ('property_id', '=', property_id)]",
        help='Rate configuration determining nightly pricing. Required for amount computation.',
    )
    package_id = fields.Many2one(
        'hospitality.package', string='Package (Ref)',
        help='Package reference',
    )
    market_segment_id = fields.Many2one(
        'hospitality.market.segment',
        string='Market Segment',
        domain="['|', ('property_id', '=', False), ('property_id', '=', property_id)]",
        help='Market segment categorization (Corporate, Leisure, Group, etc.). For sales analysis.',
    )
    source_code_id = fields.Many2one(
        'hospitality.source.code',
        string='Source Code',
        domain="['|', ('property_id', '=', False), ('property_id', '=', property_id)]",
        help='Booking source (WEB, GDS, DIRECT). For channel performance tracking.',
    )
    channel_id = fields.Many2one(
        'hospitality.channel',
        string='Channel (Ref)',
        help='Channel reference',
    )
    external_id = fields.Char(
        string='Channel Reference',
        copy=False,
        help='Reservation reference assigned by the booking channel.',
    )
    group_id = fields.Char(
        string='Group Block (Ref)',
        help='Group block reference — will be a Many2one in a future phase.',
    )
    group_id_stub = fields.Char(
        string='Group Key (Stub)',
        index=True,
        copy=False,
        help='Auto-generated group identifier for multi-room bookings. '
             'Replaced by the hospitality.group.block Many2one in Phase 2.',
    )
    share_with_ids = fields.Many2many(
        'hospitality.reservation',
        relation='reservation_share_rel',
        column1='res1_id',
        column2='res2_id',
        string='Sharers',
        help='Other reservations sharing the same room.',
    )
    guarantee_type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('credit_card', 'Credit Card'),
            ('deposit', 'Deposit'),
            ('company', 'Company'),
            ('travel_agent', 'Travel Agent'),
            ('complimentary', 'Complimentary'),
            ('house_use', 'House Use'),
        ],
        string='Guarantee Type',
        required=True,
        default='none',
        help='Guarantee method (Credit Card, Deposit, Company, etc.). Determines settlement default.',
    )
    cc_token = fields.Char(
        string='Payment Token',
        copy=False,
        groups='hospitality_reservation.group_reservation_supervisor',
        help='Encrypted card-on-file token (supervisor only).',
    )
    cancellation_policy_id = fields.Many2one(
        'hospitality.cancellation.policy',
        string='Cancellation Policy',
        domain="['|', ('property_id', '=', False), ('property_id', '=', property_id)]",
        help='Cancellation policy determining fees on cancellation.',
    )
    deposit_policy_id = fields.Many2one(
        'hospitality.deposit.policy',
        string='Deposit Policy',
        domain="['|', ('property_id', '=', False), ('property_id', '=', property_id)]",
        help='Deposit policy calculating required upfront payment.',
    )
    deposit_amount = fields.Monetary(
        string='Deposit Required',
        compute='_compute_deposit_amount',
        store=True,
        readonly=False,
        help='Computed from the deposit policy; can be overridden.',
    )
    deposit_paid = fields.Monetary(
        string='Deposit Paid',
        default=0.0,
        help='Updated by folio payments that reference this reservation.',
    )
    deposit_outstanding = fields.Boolean(
        string='Deposit Outstanding',
        compute='_compute_deposit_outstanding',
        store=True,
        help='True if deposit_paid < deposit_amount.',
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        help='Sum of nightly rates for the entire stay.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self._default_currency(),
        help='Currency used for this reservation.',
    )
    trace_count = fields.Integer(
        string='Trace Count',
        compute='_compute_trace_count',
        help='Count of unresolved traces for this reservation.',
    )
    vip_level = fields.Selection(
        selection=[
            ('none', 'None'),
            ('vip', 'VIP'),
            ('vvip', 'VVIP'),
        ],
        string='VIP Level',
        compute='_compute_vip_level',
        store=True,
        help='Sourced from the guest profile (hospitality_guest_profile) once '
             'installed; defaults to "None" otherwise.',
    )
    balance = fields.Monetary(
        string='Balance',
        compute='_compute_balance',
        store=True,
        help='Open folio balance. Always 0.00 until hospitality_folio is '
             'installed and supplies folio_ids.',
    )
    nights_remaining = fields.Integer(
        string='Nights Remaining',
        compute='_compute_nights_remaining',
        help='For in-house guests: nights between today (property business '
             'date) and departure.',
    )
    expected_departure_time = fields.Float(
        string='Expected Departure Time',
        default=lambda self: self._default_expected_departure_time(),
        help='Expected check-out time (24 h float). Editable per-stay; '
             'defaults from the property\'s configured check-out time.',
    )
    settlement_method = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('credit_card', 'Credit Card'),
            ('direct_bill', 'Direct Bill'),
            ('city_ledger', 'City Ledger'),
            ('travel_agent', 'Travel Agent'),
            ('complimentary', 'Complimentary'),
        ],
        string='Settlement Method',
        compute='_compute_settlement_method',
        store=True,
        readonly=False,
        help='Payment method at check-out. Defaults from guarantee_type, can be overridden.',
    )
    preferences = fields.Text(
        string='Guest Preferences',
        help='Narrative copy from guest preference records.',
    )
    comments = fields.Html(string='Comments', help='Free-form internal notes and special requests.', )
    created_via = fields.Selection(
        selection=[
            ('front_desk', 'Front Desk'),
            ('booking_engine', 'Booking Engine'),
            ('channel', 'Channel'),
            ('gds', 'GDS'),
            ('kiosk', 'Kiosk'),
            ('api', 'API'),
            ('rebook', 'Re-book'),
        ],
        string='Created Via',
        required=True,
        default='front_desk',
        help='Booking creation source (Front Desk, API, Booking Engine, etc.). For analytics.',
    )
    option_expires_at = fields.Datetime(
        string='Option Expires At',
        copy=False,
        help='When state=option, the hold is auto-cancelled after this datetime.',
    )
    is_walkin = fields.Boolean(string='Walk-in', default=False, help="True if its walk-in")
    is_no_show = fields.Boolean(
        string='No Show',
        default=False,
        copy=False,
        help='True if its no show',
    )
    cancelled_at = fields.Datetime(
        string='Cancelled At',
        readonly=True,
        copy=False,
        help='Timestamp when reservation was cancelled. Set automatically.',
    )
    cancelled_by = fields.Many2one(
        'res.users',
        string='Cancelled By',
        readonly=True,
        copy=False,
        help='User who cancelled the reservation. Set automatically.',
    )
    cancellation_reason = fields.Text(string='Cancellation Reason',
                                      help='Reason for cancellation. For analysis and audit.', )
    policy_charge_amount = fields.Monetary(
        string='Policy Charge',
        compute='_compute_policy_charge_amount',
        store=True,
        help='Cancellation fee computed from the cancellation policy.',
    )

    def _default_arrival_time(self):
        """Return default check-in time from the current property context."""
        property_id = self.env.context.get('default_property_id')
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if prop.default_check_in_time:
                return prop.default_check_in_time
        return 14.0

    def _default_currency(self):
        """Return default currency from the current property currency."""
        property_id = self.env.context.get('default_property_id')
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if prop.currency_id:
                return prop.currency_id
        return self.env.company.currency_id

    def _default_expected_departure_time(self):
        """Return default check-out time from the property context.
        Mirrors _default_arrival_time. Falls back to 12.0 (noon) when no
        property-level default_check_out_time is configured yet.
        """
        property_id = self.env.context.get('default_property_id')
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if 'default_check_out_time' in prop._fields and prop.default_check_out_time:
                return prop.default_check_out_time
        return 12.0

    @api.model_create_multi
    def create(self, vals_list):
        """Generate reservation sequence before creating records."""
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                property_id = vals.get('property_id')
                if property_id:
                    prop = self.env['hospitality.property'].browse(property_id)
                    if prop.sequence_reservation_id:
                        vals['name'] = prop.sequence_reservation_id.next_by_id()
                    else:
                        vals['name'] = self.env['ir.sequence'].next_by_code(
                            'hospitality.reservation'
                        ) or '/'
        return super().create(vals_list)

    @api.depends('arrival', 'departure')
    def _compute_nights(self):
        """Compute the total number of stay nights."""
        for rec in self:
            if rec.arrival and rec.departure:
                delta = fields.Date.from_string(
                    str(rec.departure)
                ) - fields.Date.from_string(str(rec.arrival))
                rec.nights = max(delta.days, 0)
            else:
                rec.nights = 0

    @api.depends(
        'rate_code_id',
        'arrival',
        'departure',
        'adults',
        'children',
        'package_id',
        'space_type_id',
        'property_id',
    )
    def _compute_total_amount(self):
        """Compute the total reservation amount from nightly rates."""
        for rec in self:
            total = 0.0
            if (
                    rec.rate_code_id
                    and rec.property_id
                    and rec.space_type_id
                    and rec.arrival
                    and rec.departure
                    and rec.nights
            ):
                result = rec.rate_code_id._get_rate(
                    rec.property_id.id,
                    rec.space_type_id.id,
                    rec.rate_code_id.id,
                    rec.arrival,
                    rec.departure,
                    {
                        'adults': rec.adults,
                        'children': rec.children,
                    },
                )
                for night_date, amount in result.get('nightly', []):
                    if amount is not None:
                        total += amount
            rec.total_amount = total

    def _get_first_night_amount(self):
        """Return the rate for just the first night of the stay, used by
        deposit policies whose amount_type is 'first_night'. Mirrors the
        per-night lookup already used in _compute_total_amount, but for
        a single date instead of looping the whole stay.
        """
        self.ensure_one()
        if not (self.rate_code_id and self.arrival):
            return 0.0
        try:
            return self.rate_code_id._get_rate(
                self.arrival, self.adults, self.space_type_id,
            )
        except Exception:
            return 0.0

    @api.depends('deposit_policy_id', 'total_amount', 'nights',
                 'rate_code_id', 'arrival', 'adults', 'space_type_id')
    def _compute_deposit_amount(self):
        """
        hospitality.deposit.policy.compute_deposit() requires
        (total_amount, first_night_amount) — two floats, NOT a
        reservation recordset. The previous version of this method
        called compute_deposit(rec), passing the reservation itself as
        total_amount and omitting first_night_amount entirely; that
        raised a TypeError on every call, which the bare except below
        silently swallowed, so deposit_amount was always 0.0 regardless
        of whether a deposit policy was actually assigned. Fixed to pass
        the real total_amount plus a first-night lookup.
        """
        for rec in self:
            if rec.deposit_policy_id and hasattr(
                    rec.deposit_policy_id, 'compute_deposit'
            ):
                try:
                    rec.deposit_amount = rec.deposit_policy_id.compute_deposit(
                        rec.total_amount, rec._get_first_night_amount()
                    )
                except Exception:
                    rec.deposit_amount = 0.0
            else:
                rec.deposit_amount = 0.0

    @api.depends('deposit_paid', 'deposit_amount')
    def _compute_deposit_outstanding(self):
        """Determine whether the required deposit is still outstanding."""
        for rec in self:
            rec.deposit_outstanding = rec.deposit_paid < rec.deposit_amount

    @api.depends('cancellation_policy_id', 'state', 'total_amount')
    def _compute_policy_charge_amount(self):
        """Compute the cancellation policy charge for cancelled reservations."""
        for rec in self:
            if (
                    rec.state == 'cancelled'
                    and rec.cancellation_policy_id
                    and hasattr(rec.cancellation_policy_id, 'compute_charge')
            ):
                try:
                    rec.policy_charge_amount = (
                        rec.cancellation_policy_id.compute_charge(rec)
                    )
                except Exception:
                    rec.policy_charge_amount = 0.0
            else:
                rec.policy_charge_amount = 0.0

    @api.model
    def _get_trace_reservation_field(self):
        """Auto-detect which field on hospitality.activity.trace points back
        to this reservation, and whether it is stored as a plain integer FK
        (Many2one) or as a 'model,id' Reference string.

        Python field introspection alone is unreliable: hospitality_base may
        declare the field as fields.Many2one('hospitality.reservation') while
        the actual PostgreSQL column stores the Reference string format
        'hospitality.reservation,<id>' — e.g. when the field was changed
        from Reference → Many2one without a DB migration.  Passing a plain
        integer to a TEXT column raises
        'invalid input syntax for type integer: hospitality.reservation,N'.

        Strategy:
        1. Find the field name via Python introspection (Many2one comodel
           match, then Reference selection match, then literal name fallback).
        2. Confirm the actual PostgreSQL column type from
           information_schema.columns.  If the column is integer/bigint we
           use 'many2one' domain; any other type (text, varchar …) means the
           data is stored in Reference format so we use 'reference' domain.

        :rtype: tuple(str, str) or False — (field_name, 'many2one'/'reference')
        """
        if 'hospitality.activity.trace' not in self.env:
            return False

        trace_model = self.env['hospitality.activity.trace']
        trace_fields = trace_model._fields
        candidate = None
        for fname, field in trace_fields.items():
            if (
                    field.type == 'many2one'
                    and field.comodel_name == 'hospitality.reservation'
            ):
                candidate = fname
                break
        if not candidate:
            for fname, field in trace_fields.items():
                if field.type != 'reference':
                    continue
                if fname == 'reservation_id':
                    candidate = fname
                    break
                selection = getattr(field, 'selection', None)
                models_in_sel = []
                if callable(selection):
                    try:
                        models_in_sel = [m for m, _ in selection(trace_model)]
                    except Exception:
                        pass
                elif selection:
                    models_in_sel = [m for m, _ in selection]
                if 'hospitality.reservation' in models_in_sel:
                    candidate = fname
                    break
        if not candidate and 'reservation_id' in trace_fields:
            candidate = 'reservation_id'
        if not candidate:
            return False
        self.env.cr.execute(
            """
            SELECT data_type
              FROM information_schema.columns
             WHERE table_name  = 'hospitality_activity_trace'
               AND column_name = %s
            """,
            [candidate],
        )
        row = self.env.cr.fetchone()
        if row:
            pg_type = row[0]
            actual_kind = 'many2one' if pg_type in ('integer', 'bigint') else 'reference'
            return (candidate, actual_kind)
        field_obj = trace_fields[candidate]
        fallback_kind = 'many2one' if field_obj.type == 'many2one' else 'reference'
        return (candidate, fallback_kind)

    def _trace_search_domain(self, rel_info, reservation_ids):
        """Build a search domain clause for hospitality.activity.trace
        matching the given reservation id(s), accounting for whether
        the relation field is a Many2one or a Reference (which Odoo
        searches differently — Reference fields compare against the
        'model,id' string form, not a bare id).

        :param tuple rel_info: (field_name, 'many2one'/'reference') as
            returned by _get_trace_reservation_field().
        :param list reservation_ids: hospitality.reservation ids to match.
        :rtype: list — an Odoo domain fragment.
        """
        fname, kind = rel_info
        if kind == 'many2one':
            return [(fname, 'in', list(reservation_ids))]
        return [
            (fname, 'in', [
                'hospitality.reservation,%d' % rid for rid in reservation_ids
            ])
        ]

    def _trace_create_context_key(self, rel_info):
        """Default-context key for pre-filling the relation field on a
        new trace via a quick-create form, for either field kind."""
        fname, _kind = rel_info
        return 'default_%s' % fname

    def _trace_create_value(self, rel_info, reservation_id):
        """Value to write into the relation field on trace creation,
        formatted correctly for either field kind."""
        fname, kind = rel_info
        if kind == 'many2one':
            return reservation_id
        return 'hospitality.reservation,%d' % reservation_id

    def _compute_trace_count(self):
        """Count unresolved traces for each reservation.

        No @api.depends: the relation field name is only known at
        runtime (see _get_trace_reservation_field), so there is no fixed
        field path to declare a dependency on. This means trace_count
        will not auto-refresh reactively on a form left open while a
        trace is added elsewhere — it recomputes on each fresh read,
        which is sufficient for a list column that's reloaded whenever
        the Arrivals list is (re)opened.
        """
        rel_info = self._get_trace_reservation_field()
        if not rel_info:
            self.trace_count = 0
            return
        trace_model = self.env['hospitality.activity.trace']
        for rec in self:
            if not rec.id:
                rec.trace_count = 0
                continue
            domain = self._trace_search_domain(rel_info, [rec.id])
            rec.trace_count = trace_model.search_count(
                domain + [('resolved', '=', False)]
            )

    @api.depends('partner_id')
    def _compute_vip_level(self):
        """Fallback: reads partner_id.vip_level if hospitality_guest_profile has
        added it; otherwise every reservation reports 'none'.

        store=True requires @api.depends to list real, already-existing
        fields, so this can only depend on 'partner_id' (not
        'partner_id.vip_level', since that field doesn't exist on
        res.partner yet). Practical effect: once hospitality_guest_profile adds
        vip_level to res.partner, changing a partner's VIP status will
        NOT automatically refresh already-stored reservation.vip_level
        values — only switching partner_id on the reservation will. A
        cron or a write() override on res.partner.vip_level can
        recompute affected reservations once that module exists; until
        then, vip_level is always 'none' so the gap has no visible
        effect today.

        Selection guard: hospitality_guest_profile's vip_level selection is not
        guaranteed to match this model's ('none'/'vip'/'vvip') — e.g. it
        may use values like 'gold'/'platinum'. Assigning an unrecognised
        value directly would raise ValueError (Wrong value for
        Selection field). Unrecognised values are mapped to 'vip' as a
        safe, visible default (better the front desk sees "VIP" than the
        record fails to compute at all) rather than silently 'none'.
        """
        known = {'none', 'vip', 'vvip'}
        for rec in self:
            partner = rec.partner_id
            raw = partner.vip_level if (
                    partner and 'vip_level' in partner._fields
            ) else False
            if not raw:
                rec.vip_level = 'none'
            elif raw in known:
                rec.vip_level = raw
            else:
                rec.vip_level = 'vip'

    @api.depends('state')
    def _compute_balance(self):
        """Fallback: sums folio_ids.balance if hospitality_folio has added
        folio_ids to this model; otherwise every reservation reports 0.00.

        store=True (see field definition above) requires @api.depends to
        list real fields that exist today; folio_ids/folio_ids.balance
        don't exist yet, so 'state' is used as the trigger instead — a
        reasonable proxy since balance only becomes meaningful around
        check-in/check-out. This means the stored value will NOT
        auto-refresh on every folio posting once hospitality_folio
        exists, only when the reservation's state changes. At that point
        replace the decorator with
        @api.depends('state', 'folio_ids', 'folio_ids.balance') so folio
        writes also trigger a recompute. Until then this is always 0.00,
        so the gap has no visible effect today.
        """
        for rec in self:
            if 'folio_ids' in rec._fields:
                rec.balance = sum(rec.folio_ids.mapped('balance'))
            else:
                rec.balance = 0.0

    @api.depends('departure', 'property_id')
    def _compute_nights_remaining(self):
        """Nights between the property's business_date and departure,
        floored at 0. Uses business_date (not wall-clock today) per the
        RES-04 acceptance criteria — see _get_business_date().
        """
        for rec in self:
            if not rec.departure:
                rec.nights_remaining = 0
                continue
            today = rec._get_business_date()
            delta = rec.departure - today
            rec.nights_remaining = max(delta.days, 0)

    @api.depends('guarantee_type')
    def _compute_settlement_method(self):
        """Seed settlement_method from guarantee_type on first compute;
        stored + readonly=False so a front desk agent's manual override
        sticks (Odoo only re-runs the compute when a dependency changes).
        """
        mapping = {
            'credit_card': 'credit_card',
            'company': 'direct_bill',
            'travel_agent': 'travel_agent',
            'complimentary': 'complimentary',
            'house_use': 'complimentary',
            'deposit': 'cash',
            'none': 'cash',
        }
        for rec in self:
            rec.settlement_method = mapping.get(rec.guarantee_type, 'cash')

    @api.constrains('arrival', 'departure')
    def _check_dates(self):
        """Ensure the departure date is after the arrival date."""
        for rec in self:
            if rec.arrival and rec.departure and rec.departure <= rec.arrival:
                raise ValidationError(
                    'Departure date must be strictly after arrival date.'
                )

    @api.constrains('adults')
    def _check_adults(self):
        """Ensure at least one adult is included in the reservation."""
        for rec in self:
            if rec.adults < 1:
                raise ValidationError('At least 1 adult is required.')

    @api.constrains('space_id', 'space_type_id')
    def _check_space_type_match(self):
        """Validate that the assigned space matches the selected space type."""
        for rec in self:
            if rec.space_id and rec.space_type_id:
                if rec.space_id.space_type_id != rec.space_type_id:
                    raise ValidationError(
                        'The assigned room "%s" belongs to type "%s", '
                        'but the reservation requires "%s".'
                        % (
                            rec.space_id.name,
                            rec.space_id.space_type_id.name,
                            rec.space_type_id.name,
                        )
                    )
    @api.constrains('state', 'space_id')
    def _check_checkin_requires_space(self):
        """Prevent check-in when no space has been assigned."""
        for rec in self:
            if rec.state == 'checked_in' and not rec.space_id:
                raise ValidationError(
                    'Cannot check in without an assigned room.'
                )

    @api.constrains('share_with_ids', 'arrival', 'departure', 'space_id')
    def _check_sharer_overlap(self):
        """Validate sharers have overlapping stays in the same space."""
        for rec in self:
            for sharer in rec.share_with_ids:
                if rec.arrival and rec.departure:
                    if (
                            sharer.departure <= rec.arrival
                            or sharer.arrival >= rec.departure
                    ):
                        raise ValidationError(
                                'Sharer reservation %(name)s does not '
                                'overlap in dates.',
                                name=sharer.name,
                        )
                if rec.space_id and sharer.space_id:
                    if rec.space_id != sharer.space_id:
                        raise ValidationError(
                                'Sharer reservation %(name)s must be '
                                'assigned to the same room.',
                                name=sharer.name,
                        )

    def _lock_parent_space(self):
        """Lock the parent space when a child space is confirmed."""
        for reservation in self:
            space = reservation.space_id
            if (
                    space
                    and space.lock_parent_when_child_booked
                    and space.parent_space_id
            ):
                space.parent_space_id.status = 'oos'

    def _unlock_parent_space(self):
        """Unlock the parent space when no active child reservation remains."""
        for reservation in self:
            space = reservation.space_id
            if not (
                    space
                    and space.lock_parent_when_child_booked
                    and space.parent_space_id
            ):
                continue
            parent = space.parent_space_id
            active_child_reservation = self.search_count([
                ('id', 'not in', self.ids),
                ('space_id.parent_space_id', '=', parent.id),
                ('state', 'in', ('confirmed', 'checked_in')),
            ])
            if not active_child_reservation:
                parent.status = 'vacant_clean'

    def action_save_option(self):
        """Set draft → option (requires option_expires_at)."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    'Only draft reservations can be placed on option.'
                )
            if not rec.option_expires_at:
                raise UserError(
                    'Please set an option expiry date/time before saving as option.'
                )
            rec.state = 'option'
        return True

    def action_confirm(self):
        """Set draft/option → confirmed; validates deposit if policy requires."""
        for rec in self:
            if rec.state not in ('draft', 'option'):
                raise UserError(
                    'Only draft or option reservations can be confirmed.'
                )
            if not self.env.user.has_group(
                    'hospitality_reservation.group_reservation_supervisor'
            ):
                if rec.deposit_policy_id and rec.deposit_amount > 0:
                    if rec.deposit_paid < rec.deposit_amount:
                        raise UserError(
                            f"Deposit of {rec.deposit_amount} {rec.currency_id.name} "
                            f"is required before confirmation. "
                            f"Paid so far: {rec.deposit_paid}."
                        )
            rec.state = 'confirmed'
            rec._lock_parent_space()
        return True

    def action_walk_guest(self):
        """RES-04: "Walk Guest" header button on the Arrivals list.

        Opens this reservation's form on the Stay page so the agent can
        reassign space_type_id/space_id (e.g. the booked room type is
        unavailable and the guest is being "walked" to another
        property/room category). Re-uses _space_availability_check via
        the existing space_id domain on the form — no separate wizard
        needed for this minimal version.
        """
        if len(self) != 1:
            raise UserError(
                'Please select exactly one reservation to walk.'
            )
        return {
            'type': 'ir.actions.act_window',
            'name': self.display_name,
            'res_model': 'hospitality.reservation',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit'},
        }

    def action_print_reg_card(self):
        """Print Reg Card - header button on the Arrivals list.

        The registration-card report itself is built in FD-06 (Front
        Desk module), which does not exist yet in this codebase. This
        stub keeps the button wired and gives a clear, actionable
        message instead of a missing-action/missing-report error.
        """
        raise UserError(
                'Registration card printing is provided by the Front '
                'Desk module (FD-06), which is not installed yet.'
        )

    def action_check_in(self):
        """confirmed → checked_in; guards: space_id set, deposit met."""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    'Only confirmed reservations can be checked in.'
                )
            if not rec.space_id:
                raise UserError(
                    'Please assign a room before checking in.'
                )
            if rec.deposit_policy_id and rec.deposit_amount > 0:
                if rec.deposit_paid < rec.deposit_amount:
                    raise UserError(
                        'Deposit not fully collected. Required: %s, Paid: %s.' % (
                            rec.deposit_amount,
                            rec.deposit_paid
                        )
                    )
            rec.state = 'checked_in'
            if 'hospitality.folio' in self.env:
                try:
                    self.env['hospitality.folio'].open(rec)
                except Exception:
                    pass
        return True

    def action_check_out(self):
        """Set checked_in → checked_out; guard: folio balance = 0 or rolled to AR."""
        for rec in self:
            if rec.state != 'checked_in':
                raise UserError(
                    'Only checked-in reservations can be checked out.'
                )
            if 'hospitality.folio' in self.env:
                try:
                    self.env['hospitality.folio'].close(rec)
                except Exception:
                    pass
            rec.state = 'checked_out'
        return True

    def action_add_trace(self):
        """Add Trace -  header button on the Arrivals list.

        Opens a quick-create form for hospitality.activity.trace
        (owned by hospitality_base, BASE-05) pre-filled with this
        reservation, so a front desk agent can log a request (e.g.
        "guest asked for late check-out") without leaving the list.
        """
        if len(self) != 1:
            raise UserError(
                'Please select exactly one reservation to add a trace to.'
            )
        if 'hospitality.activity.trace' not in self.env:
            raise UserError(
                    'Traces require the hospitality_base module '
                    '(BASE-05), which is not installed.'
            )
        rel_info = self._get_trace_reservation_field()
        if not rel_info:
            raise UserError(
                    'Could not determine how hospitality.activity.trace '
                    'links back to reservations — please check the '
                    'hospitality_base module.'
            )
        context = {
            self._trace_create_context_key(rel_info):
                self._trace_create_value(rel_info, self.id)
        }
        trace_fields = self.env['hospitality.activity.trace']._fields
        if 'type' in trace_fields:
            context['default_type'] = 'front_desk'
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Trace',
            'res_model': 'hospitality.activity.trace',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_add_share(self):
        """Open the Add Sharer wizard for this reservation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Sharer',
            'res_model': 'hospitality.reservation.share.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_reservation_id': self.id,
            },
        }

    def action_add_another_room(self):
        """Create a sister reservation for a multi-room booking.

        The sister shares the same partner, arrival/departure, and property
        but gets a fresh space assignment so the agent can pick a different
        room. Both reservations are linked by the same group_id_stub so they
        can be queried together as a group.

        Multi-room sisters are NOT linked via share_with_ids — that
        relationship is for two guests sharing the same physical space with
        separate folios. Group members intentionally occupy different spaces.
        """
        self.ensure_one()
        if not self.group_id_stub:
            stub = str(uuid.uuid4()).replace('-', '')[:20].upper()
            self.group_id_stub = stub
        else:
            stub = self.group_id_stub
        sister = self.copy(default={
            'space_id': False,
            'share_with_ids': [(5, 0, 0)],
            'state': 'draft',
            'group_id_stub': stub,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Sister Reservation',
            'res_model': 'hospitality.reservation',
            'res_id': sister.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_cancel(self):
        """confirmed/option/draft → cancelled; applies cancellation policy."""
        for rec in self:
            if rec.state not in ('draft', 'option', 'confirmed'):
                raise UserError(
                    'Only draft, option, or confirmed reservations can be cancelled.'
                )
            if (
                    rec.cancellation_policy_id
                    and hasattr(rec.cancellation_policy_id, 'compute_charge')
            ):
                try:
                    rec.cancellation_policy_id.compute_charge(rec)
                except Exception:
                    pass
            rec.write({
                'state': 'cancelled',
                'cancelled_at': fields.Datetime.now(),
                'cancelled_by': self.env.uid,
            })
        return True

    def action_no_show(self):
        """confirmed → no_show (supervisor or night audit)."""
        supervisor_group = 'hospitality_reservation.group_reservation_supervisor'
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    'Only confirmed reservations can be marked as no-show.'
                )
            if not self.env.user.has_group(supervisor_group):
                raise UserError(
                    'Only a Reservation Supervisor can mark a no-show.'
                )
            rec.write({'state': 'no_show', 'is_no_show': True})
        return True

    def action_undo_check_in(self):
        """checked_in → confirmed (supervisor only, same day)."""
        supervisor_group = 'hospitality_reservation.group_reservation_supervisor'
        today = fields.Date.today()
        for rec in self:
            if rec.state != 'checked_in':
                raise UserError(
                    'Only checked-in reservations can be undone.'
                )
            if not self.env.user.has_group(supervisor_group):
                raise UserError(
                    'Only a Reservation Supervisor can undo a check-in.'
                )
            if rec.arrival != today:
                raise UserError(
                    'Check-in can only be undone on the same day as arrival.'
                )
            rec.state = 'confirmed'
        return True

    def _get_business_date(self):
        """Return the operating "today" for this reservation's property.

        hospitality_property is expected to eventually expose
        business_date (the hotel's current operating day, advanced by
        night audit — which can run ahead of or lag wall-clock midnight).
        Until that field exists, wall-clock today is used as a safe
        fallback so this module installs and the lists remain usable on
        its own.

        IMPORTANT: this is the single choke point the Arrivals/In-House/
        Departures actions go through for "today" — do not call
        fields.Date.today() directly in new front-office code. Once
        hospitality_property adds business_date, only this method needs
        to change for every list/report to start respecting it.

        :rtype: date
        """
        self.ensure_one()
        prop = self.property_id
        if prop and 'business_date' in prop._fields and prop.business_date:
            return prop.business_date
        return fields.Date.context_today(self)

    @api.model
    def _get_business_date_for_property(self, property_id):
        """Non-recordset variant of _get_business_date(), for use in
        action domains/contexts where no reservation is bound yet (e.g.
        the Arrivals/Departures action defaults below).

        :param int property_id: hospitality.property id, or False
        :rtype: date
        """
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if 'business_date' in prop._fields and prop.business_date:
                return prop.business_date
        return fields.Date.context_today(self)

    @api.model
    def _get_current_property_id(self):
        """Resolve "current property" for front office actions.

        Reuses the same resolution order as
        get_default_tape_chart_property_id (RES-03): prefer a property
        the user is restricted to, otherwise the first property visible
        to them.

        :rtype: int or False
        """
        return self.get_default_tape_chart_property_id()

    @api.model
    def action_open_arrivals(self):
        """RES-04: server-computed opener for the Arrivals menu.

        ir.actions.act_window domains are evaluated in a restricted
        safe-eval context that cannot call ORM methods, so the
        business-date-aware domain is built here in Python and the full
        action dict is returned directly — the same pattern already used
        by action_add_trace/action_walk_guest above — rather than being
        written into the static action record's XML domain.
        """
        property_id = self._get_current_property_id()
        business_date = self._get_business_date_for_property(property_id)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Arrivals',
            'res_model': 'hospitality.reservation',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hospitality_reservation.view_reservation_arrivals_list').id, 'list'),
                (False, 'form'),
            ],
            'search_view_id': [
                self.env.ref('hospitality_reservation.view_reservation_arrivals_search').id, 'search'
            ],
            'domain': [
                ('state', '=', 'confirmed'),
                ('property_id', '=', property_id),
                ('arrival', '=', business_date),
            ],
            'context': {'search_default_group_space_type': 0},
        }

    @api.model
    def action_open_in_house(self):
        """server-computed opener for the In-House menu."""
        property_id = self._get_current_property_id()
        return {
            'type': 'ir.actions.act_window',
            'name': 'In-House',
            'res_model': 'hospitality.reservation',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hospitality_reservation.view_reservation_in_house_list').id, 'list'),
                (False, 'form'),
            ],
            'search_view_id': [
                self.env.ref('hospitality_reservation.view_reservation_in_house_search').id, 'search'
            ],
            'domain': [
                ('state', '=', 'checked_in'),
                ('property_id', '=', property_id),
            ],
            'context': {'search_default_group_space': 1},
        }

    @api.model
    def action_open_departures(self):
        """server-computed opener for the Departures menu."""
        property_id = self._get_current_property_id()
        business_date = self._get_business_date_for_property(property_id)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Departures',
            'res_model': 'hospitality.reservation',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('hospitality_reservation.view_reservation_departures_list').id, 'list'),
                (False, 'form'),
            ],
            'search_view_id': [
                self.env.ref('hospitality_reservation.view_reservation_departures_search').id, 'search'
            ],
            'domain': [
                ('state', '=', 'checked_in'),
                ('property_id', '=', property_id),
                ('departure', '=', business_date),
            ],
            'context': {},
        }

    @api.model
    def action_open_trace_pickup(self):
        """RES-04: server-computed opener for the Trace Pickup menu.

        hospitality.activity.trace is owned by hospitality_base
        (BASE-05). This module no longer defines its own views/action
        for it — instead this reuses hospitality_base's own action
        (trying a couple of likely external IDs, since the exact one
        isn't guaranteed) and only adds an "unresolved" + current
        property pre-filter on top, via domain/context, rather than
        redeclaring views this module doesn't own.
        """
        if 'hospitality.activity.trace' not in self.env:
            raise UserError(
                    'Trace Pickup requires the hospitality_base module '
                    '(BASE-05), which is not installed.'
            )
        action = False
        for xml_id in (
                'hospitality_base.action_hospitality_activity_trace',
                'hospitality_base.action_activity_trace',
        ):
            try:
                action = self.env['ir.actions.act_window']._for_xml_id(xml_id)
                break
            except ValueError:
                continue

        if not action:
            action = {
                'type': 'ir.actions.act_window',
                'name': 'Trace Pickup',
                'res_model': 'hospitality.activity.trace',
                'view_mode': 'list,form',
            }
        trace_fields = self.env['hospitality.activity.trace']._fields
        domain = []
        if 'resolved' in trace_fields:
            domain.append(('resolved', '=', False))
        if 'property_id' in trace_fields:
            property_id = self._get_current_property_id()
            domain.append(('property_id', '=', property_id))
        action['name'] = 'Trace Pickup'
        action['domain'] = domain
        return action

    def _space_availability_check(self, property_id, space_type_id, arrival, departure):
        """Return available spaces; excludes overlapping bookings
        and parents locked by child bookings.
        """
        domain = [
            ('property_id', '=', property_id),
            ('space_type_id', '=', space_type_id),
            ('status', 'not in', ['ooo', 'oos']),
        ]
        all_spaces = self.env['hospitality.space'].search(domain)
        occupied_ids = self.env['hospitality.reservation'].search([
            ('property_id', '=', property_id),
            ('space_type_id', '=', space_type_id),
            ('state', 'in', ('confirmed', 'checked_in')),
            ('arrival', '<', departure),
            ('departure', '>', arrival),
            ('space_id', '!=', False),
            ('id', 'not in', self.ids),
        ]).mapped('space_id').ids
        locked_parent_ids = self.env['hospitality.reservation'].search([
            ('property_id', '=', property_id),
            ('state', 'in', ('confirmed', 'checked_in')),
            ('arrival', '<', departure),
            ('departure', '>', arrival),
            ('space_id', '!=', False),
            ('space_id.lock_parent_when_child_booked', '=', True),
            ('space_id.parent_space_id', '!=', False),
            ('id', 'not in', self.ids),
        ]).mapped('space_id.parent_space_id').ids
        unavailable_ids = set(occupied_ids) | set(locked_parent_ids)
        return all_spaces.filtered(
            lambda space: space.id not in unavailable_ids
        )

    def _assign_space(self, space_id):
        """Assign space with row-level lock to prevent double-booking."""
        self.ensure_one()
        if not space_id:
            raise UserError('No room provided for assignment.')
        self.env.cr.execute(
            'SELECT id FROM hospitality_space WHERE id = %s FOR UPDATE',
            (space_id,),
        )
        conflict = self.env['hospitality.reservation'].search([
            ('space_id', '=', space_id),
            ('state', 'in', ('confirmed', 'checked_in')),
            ('arrival', '<', self.departure),
            ('departure', '>', self.arrival),
            ('id', '!=', self.id),
        ], limit=1)
        if conflict:
            raise UserError(
                'Room is no longer available — it was just assigned to '
                'reservation %(name)s.',
                name=conflict.name,
            )
        parent_space = self.env['hospitality.space'].browse(space_id)
        if parent_space:
            child_conflict = self.env['hospitality.reservation'].search([
                ('space_id.parent_space_id', '=', space_id),
                ('space_id.lock_parent_when_child_booked', '=', True),
                ('state', 'in', ('confirmed', 'checked_in')),
                ('arrival', '<', self.departure),
                ('departure', '>', self.arrival),
                ('id', '!=', self.id),
            ], limit=1)
            if child_conflict:
                raise UserError(
                    'Room is no longer available — its child room is already '
                    'booked by reservation %(name)s.',
                    name=child_conflict.name,
                )
        self.space_id = space_id

    @api.model
    def _cron_expire_options(self):
        """Daily cron: auto-cancel option reservations past their expiry.

        RES-05 full implementation:
        • Search for state=option whose option_expires_at < now.
        • Call action_cancel() via the normal state-machine method so all
          guards, policy charges, and chatter posts run identically to a
          manual cancellation.
        • Post a dedicated chatter note so the audit trail is explicit.
        • Sets policy_charge_amount=0 because expiry is not a guest-initiated
          cancellation (no penalty applies).
        """
        now = fields.Datetime.now()
        expired = self.search([
            ('state', '=', 'option'),
            ('option_expires_at', '<', now),
        ])
        reason = 'Option expired automatically.'
        for res in expired:
            res.write({'cancellation_reason': reason})
            try:
                res.action_cancel()
            except Exception:
                res.write({
                    'state': 'cancelled',
                    'cancelled_at': now,
                    'cancelled_by': self.env.uid,
                })
            res.message_post(
                body='Option reservation automatically cancelled: '
                       'option_expires_at %s was reached.' % res.option_expires_at,
                subtype_xmlid='mail.mt_note',
            )

    @api.model
    def get_default_tape_chart_property_id(self):
        """Resolve which property the Tape Chart should open on for the
        current user when none was supplied via context.

        Server-side on purpose: self.env.uid is always the correctly
        authenticated user for this request, unlike client-side session
        globals which may not be populated the same way in every mount
        context. Prefers a property the user is actually assigned to
        (res.users.property_ids) so a restricted agent doesn't land on
        an arbitrary property (e.g. whichever one happens to have the
        lowest id) that has no spaces or reservations visible to them.
        Returns False when the user has no allowed properties.

        :rtype: int or False
        """
        user = self.env.user
        if 'property_ids' in user._fields and user.property_ids:
            return user.property_ids[0].id
        return False

    @api.model
    def get_tape_chart_data(self, property_id, date_from, date_to):
        """Single read for the Tape Chart front end.

        Returns spaces (rows), reservations overlapping [date_from, date_to),
        and OOO/OOS blocks for the given property, in one payload so the
        widget does not need multiple round trips.

        :param int property_id: hospitality.property id
        :param str date_from: 'YYYY-MM-DD'
        :param str date_to: 'YYYY-MM-DD' (exclusive upper bound)
        :rtype: dict
        """
        if not property_id:
            return {'spaces': [], 'space_types': [], 'reservations': [], 'ooo_blocks': []}
        date_from = fields.Date.from_string(date_from)
        date_to = fields.Date.from_string(date_to)
        spaces = self.env['hospitality.space'].search([
            ('property_id', '=', property_id),
        ], order='space_type_id, name')
        space_types = spaces.mapped('space_type_id')
        space_data = [{
            'id': space.id,
            'name': space.name,
            'space_type_id': space.space_type_id.id,
            'space_type_name': space.space_type_id.name,
            'state': space.status,
        } for space in spaces]
        space_type_data = [{
            'id': stype.id,
            'name': stype.name,
            'space_count': len(spaces.filtered(
                lambda s: s.space_type_id.id == stype.id
            )),
        } for stype in space_types]
        reservations = self.search([
            ('property_id', '=', property_id),
            ('arrival', '<', date_to),
            ('departure', '>', date_from),
            ('state', '!=', 'cancelled'),
        ])
        reservation_data = [{
            'id': res.id,
            'name': res.name,
            'partner_name': res.partner_id.display_name,
            'space_id': res.space_id.id if res.space_id else False,
            'space_type_id': res.space_type_id.id,
            'arrival': fields.Date.to_string(res.arrival),
            'departure': fields.Date.to_string(res.departure),
            'state': res.state,
            'adults': res.adults,
            'children': res.children,
            'is_walkin': res.is_walkin,
        } for res in reservations]
        ooo_blocks = []
        for space in spaces.filtered(
                lambda s: s.status in ('out_of_order', 'out_of_service')
        ):
            ooo_blocks.append({
                'space_id': space.id,
                'state': space.status,
                'date_from': fields.Date.to_string(date_from),
                'date_to': fields.Date.to_string(date_to),
            })
        return {
            'spaces': space_data,
            'space_types': space_type_data,
            'reservations': reservation_data,
            'ooo_blocks': ooo_blocks,
        }
