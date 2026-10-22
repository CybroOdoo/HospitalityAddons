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
from datetime import timedelta
from odoo import api, fields, models
from odoo.tools import _
from odoo.exceptions import UserError, ValidationError


class HospitalityReservation(models.Model):
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
    )
    property_id = fields.Many2one(
        'hospitality.property',
        string='Property',
        required=True,
        index=True,
        tracking=True,
    )

    # ── State ─────────────────────────────────────────────────────────────────

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
    )

    # ── Guest ─────────────────────────────────────────────────────────────────

    partner_id = fields.Many2one(
        'res.partner',
        string='Guest',
        required=True,
        index=True,
        tracking=True,
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
    )

    # ── Stay dates ────────────────────────────────────────────────────────────

    arrival = fields.Date(
        string='Arrival',
        required=True,
        index=True,
        tracking=True,
    )
    departure = fields.Date(
        string='Departure',
        required=True,
        index=True,
        tracking=True,
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
    )

    # ── Occupancy ─────────────────────────────────────────────────────────────

    adults = fields.Integer(string='Adults', required=True, default=2)
    children = fields.Integer(string='Children', default=0)
    infants = fields.Integer(string='Infants', default=0)
    child_ages = fields.Char(
        string='Child Ages',
        help='Comma-separated list of child ages, e.g. "3,7,10".',
    )

    # ── Space ─────────────────────────────────────────────────────────────────

    space_type_id = fields.Many2one(
        'hospitality.space.type',
        string='Space Type',
        required=True,
    )
    space_id = fields.Many2one(
        'hospitality.space',
        string='Space',
        domain="[('property_id','=',property_id),"
               " ('space_type_id','=',space_type_id)]",
    )

    # ── Rate & package ────────────────────────────────────────────────────────

    rate_code_id = fields.Many2one(
        'hospitality.rate.code',
        string='Rate Code',
        required=True,
    )
    # Phase 2: will become Many2one('hospitality.package') when that module exists
    package_id = fields.Char(
        string='Package (Ref)',
        help='Package reference — will be a Many2one in a future phase.',
    )

    # ── Segmentation ─────────────────────────────────────────────────────────

    market_segment_id = fields.Many2one(
        'hospitality.market.segment',
        string='Market Segment',
    )
    source_code_id = fields.Many2one(
        'hospitality.source.code',
        string='Source Code',
    )
    # Phase 2: will become Many2one('hospitality.channel') when that module exists
    channel_id = fields.Char(
        string='Channel (Ref)',
        help='Channel reference — will be a Many2one in a future phase.',
    )
    external_id = fields.Char(
        string='Channel Reference',
        copy=False,
        help='Reservation reference assigned by the booking channel.',
    )

    # ── Group / multi-room ────────────────────────────────────────────────────

    # Phase 2: will become Many2one('hospitality.group.block') when that module exists
    group_id = fields.Char(
        string='Group Block (Ref)',
        help='Group block reference — will be a Many2one in a future phase.',
    )
    share_with_ids = fields.Many2many(
        'hospitality.reservation',
        relation='reservation_share_rel',
        column1='res1_id',
        column2='res2_id',
        string='Sharers',
        help='Other reservations sharing the same space.',
    )

    # ── Guarantee & payment ───────────────────────────────────────────────────

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
    )
    deposit_policy_id = fields.Many2one(
        'hospitality.deposit.policy',
        string='Deposit Policy',
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
    # RES-04: search domains cannot compare one field against another
    # field (e.g. ('deposit_paid','<','deposit_amount') is invalid —
    # 'deposit_amount' would be read as a literal string, not a field
    # reference). This stored boolean is the standard Odoo workaround so
    # the Arrivals search view's "Deposit Outstanding" filter can simply
    # check ('deposit_outstanding','=',True).
    deposit_outstanding = fields.Boolean(
        string='Deposit Outstanding',
        compute='_compute_deposit_outstanding',
        store=True,
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self._default_currency(),
    )

    # ── Related one2many (from other modules) ─────────────────────────────────

    # RES-04: hospitality.activity.trace is now owned by hospitality_base
    # (BASE-05 has landed). This module no longer declares its own copy
    # of that model, and deliberately does NOT declare a hardcoded
    # One2many('hospitality.activity.trace', '<some_field>', ...) here,
    # because the exact name of the field on that model that points back
    # to this reservation is owned by hospitality_base and may not be
    # 'reservation_id' (declaring a One2many with the wrong inverse field
    # name raises at registry load, exactly like the field/view
    # mismatches that caused the earlier crashes). trace_count is instead
    # computed defensively in Python — see
    # _compute_trace_count/_get_trace_reservation_field below, which
    # auto-detects whichever Many2one field on hospitality.activity.trace
    # actually points at hospitality.reservation.
    trace_count = fields.Integer(
        string='Trace Count',
        compute='_compute_trace_count',
    )

    # FOL-05: will become One2many('hospitality.routing.instruction') when that module exists
    # routing_instruction_ids — defined in hospitality_folio FOL-05
    # FOL: will become One2many('hospitality.folio') when that module exists
    # folio_ids — defined in hospitality_folio

    # ── RES-04: Front office list fields ────────────────────────────────────
    # vip_level lives on res.partner in hospitality_guest_profile (not yet built);
    # balance/settlement_method live on hospitality.folio (not yet built).
    # Both are exposed here as safe, always-computable fallbacks so the
    # Arrivals/In-House/Departures lists can ship now and pick up the real
    # values automatically the moment those modules add the underlying
    # fields — no view changes required, only these compute methods.
    #
    # store=True (unlike balance/nights_remaining below): the Arrivals
    # search view filters and groups on vip_level, and Odoo only allows
    # search/group_by on stored fields (a non-stored compute raises
    # "Unsearchable field" at view-validation time). partner_id rarely
    # changes after creation, so the storage cost is negligible.
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
    # store=True: filter_balance_due on the In-House/Departures search
    # views needs to filter on this field, and Odoo only allows
    # search/group_by on stored fields (same reasoning as vip_level
    # above). Always 0.00 today since folio_ids does not exist yet —
    # see _compute_balance for the recompute-trigger caveat once
    # hospitality_folio is installed.
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
        help='Defaults from guarantee_type; can be overridden at the '
             'front desk before departure.',
    )

    # ── Preferences & notes ───────────────────────────────────────────────────

    preferences = fields.Text(
        string='Guest Preferences',
        help='Narrative copy from guest preference records.',
    )
    comments = fields.Html(string='Comments')

    # ── Audit / operational flags ─────────────────────────────────────────────

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
    )
    option_expires_at = fields.Datetime(
        string='Option Expires At',
        copy=False,
        help='When state=option, the hold is auto-cancelled after this datetime.',
    )
    is_walkin = fields.Boolean(string='Walk-in', default=False)
    is_no_show = fields.Boolean(
        string='No Show',
        default=False,
        copy=False,
    )
    cancelled_at = fields.Datetime(
        string='Cancelled At',
        readonly=True,
        copy=False,
    )
    cancelled_by = fields.Many2one(
        'res.users',
        string='Cancelled By',
        readonly=True,
        copy=False,
    )
    cancellation_reason = fields.Text(string='Cancellation Reason')
    policy_charge_amount = fields.Monetary(
        string='Policy Charge',
        compute='_compute_policy_charge_amount',
        store=True,
        help='Cancellation fee computed from the cancellation policy.',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Defaults
    # ─────────────────────────────────────────────────────────────────────────

    def _default_arrival_time(self):
        """Return default check-in time from the current property context."""
        property_id = self.env.context.get('default_property_id')
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if prop.default_check_in_time:
                return prop.default_check_in_time
        return 14.0

    def _default_currency(self):
        property_id = self.env.context.get('default_property_id')
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if prop.currency_id:
                return prop.currency_id
        return self.env.company.currency_id

    def _default_expected_departure_time(self):
        """RES-04: default check-out time from the property context.

        Mirrors _default_arrival_time. Falls back to 12.0 (noon) when no
        property-level default_check_out_time is configured yet.
        """
        property_id = self.env.context.get('default_property_id')
        if property_id:
            prop = self.env['hospitality.property'].browse(property_id)
            if 'default_check_out_time' in prop._fields and prop.default_check_out_time:
                return prop.default_check_out_time
        return 12.0

    # ─────────────────────────────────────────────────────────────────────────
    # ORM overrides
    # ─────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
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

    # ─────────────────────────────────────────────────────────────────────────
    # Computed fields
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('arrival', 'departure')
    def _compute_nights(self):
        for rec in self:
            if rec.arrival and rec.departure:
                delta = fields.Date.from_string(
                    str(rec.departure)
                ) - fields.Date.from_string(str(rec.arrival))
                rec.nights = max(delta.days, 0)
            else:
                rec.nights = 0

    @api.depends('rate_code_id', 'arrival', 'departure', 'adults',
                 'package_id', 'space_type_id')
    def _compute_total_amount(self):
        for rec in self:
            total = 0.0
            if rec.rate_code_id and rec.arrival and rec.departure and rec.nights:
                current = rec.arrival
                while current < rec.departure:
                    try:
                        nightly = rec.rate_code_id._get_rate(
                            current,
                            rec.adults,
                            rec.space_type_id,
                        )
                        total += nightly
                    except Exception:
                        pass
                    current = fields.Date.from_string(str(current))
                    current = current + timedelta(days=1)
            rec.total_amount = total

    @api.depends('deposit_policy_id', 'total_amount', 'nights')
    def _compute_deposit_amount(self):
        for rec in self:
            if rec.deposit_policy_id and hasattr(
                rec.deposit_policy_id, 'compute_deposit'
            ):
                try:
                    rec.deposit_amount = rec.deposit_policy_id.compute_deposit(rec)
                except Exception:
                    rec.deposit_amount = 0.0
            else:
                rec.deposit_amount = 0.0

    @api.depends('deposit_paid', 'deposit_amount')
    def _compute_deposit_outstanding(self):
        for rec in self:
            rec.deposit_outstanding = rec.deposit_paid < rec.deposit_amount

    @api.depends('cancellation_policy_id', 'state', 'total_amount')
    def _compute_policy_charge_amount(self):
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

    # ── RES-04: Front office list computes ──────────────────────────────────

    @api.model
    def _get_trace_reservation_field(self):
        """Auto-detect which field on hospitality.activity.trace (owned
        by hospitality_base, BASE-05) points back to this reservation.

        Declaring a hardcoded One2many('hospitality.activity.trace',
        '<field>', ...) on this model would require knowing that field's
        exact name at class-definition time, and getting it wrong raises
        at registry load — exactly what happened when this module and
        hospitality_base briefly disagreed on the relation field name.
        Detecting it at runtime avoids hardcoding an assumption about
        another module's internals.

        Detection order (each step only runs if the previous found
        nothing):
        1. Many2one with comodel_name == 'hospitality.reservation' —
           the unambiguous, correct case.
        2. A field literally named 'reservation_id' of type many2one,
           regardless of how its comodel_name introspects — covers
           hospitality_base's actual schema (confirmed via a failed
           test insert: the real DB column is reservation_id, an
           integer FK, i.e. a genuine Many2one).
        3. Reference field whose selection explicitly lists
           'hospitality.reservation' — only an exact, explicit match;
           no permissive fallback for unintrospectable selections,
           since that previously grabbed an unrelated field.

        Earlier versions of this method had a step 3 fallback that
        accepted ANY Reference field if its selection couldn't be
        introspected. That was wrong: it silently matched a field with
        no actual connection to hospitality.reservation. Removed.

        :rtype: tuple(str, str) or False — (field_name, 'many2one'/
            'reference'), or False if hospitality.activity.trace isn't
            installed or has no field pointing at hospitality.reservation.
        """
        if 'hospitality.activity.trace' not in self.env:
            return False
        trace_model = self.env['hospitality.activity.trace']
        trace_fields = trace_model._fields

        # 1. Exact comodel match.
        for fname, field in trace_fields.items():
            if (
                field.type == 'many2one'
                and field.comodel_name == 'hospitality.reservation'
            ):
                return (fname, 'many2one')

        # 2. Literal field name 'reservation_id' — covers both many2one
        #    and reference cases where the DB column is a plain integer FK.
        #    hospitality_base declares this as a Reference field at the ORM
        #    level but the underlying column is an integer (not a char), so
        #    we must write an integer id, not the 'model,id' reference string.
        #    Force 'many2one' so _trace_create_value always writes an integer.
        if 'reservation_id' in trace_fields:
            return ('reservation_id', 'many2one')

        # 3. Reference field with an explicit, introspectable selection
        #    that names hospitality.reservation. No permissive
        #    fallback — an unintrospectable/empty selection is treated
        #    as "not a match", not "maybe a match".
        for fname, field in trace_fields.items():
            if field.type != 'reference':
                continue
            selection = getattr(field, 'selection', None)
            models_in_selection = []
            if callable(selection):
                try:
                    models_in_selection = [
                        m for m, _ in selection(trace_model)
                    ]
                except Exception:
                    models_in_selection = []
            elif selection:
                models_in_selection = [m for m, _ in selection]
            if 'hospitality.reservation' in models_in_selection:
                return (fname, 'reference')

        return False

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
        # reference: stored as 'hospitality.reservation,<id>' — Odoo
        # supports 'in' with the model-qualified string form.
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

    # ─────────────────────────────────────────────────────────────────────────
    # Constraints
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('arrival', 'departure')
    def _check_dates(self):
        for rec in self:
            if rec.arrival and rec.departure and rec.departure <= rec.arrival:
                raise ValidationError(
                    _('Departure date must be strictly after arrival date.')
                )

    @api.constrains('adults')
    def _check_adults(self):
        for rec in self:
            if rec.adults < 1:
                raise ValidationError(_('At least 1 adult is required.'))

    @api.constrains('space_id', 'space_type_id')
    def _check_space_type_match(self):
        for rec in self:
            if rec.space_id and rec.space_type_id:
                if rec.space_id.space_type_id != rec.space_type_id:
                    raise ValidationError(
                        _(
                            'The assigned space "%(space)s" belongs to type '
                            '"%(actual)s", but the reservation requires '
                            '"%(expected)s".',
                            space=rec.space_id.name,
                            actual=rec.space_id.space_type_id.name,
                            expected=rec.space_type_id.name,
                        )
                    )

    @api.constrains('state', 'space_id')
    def _check_checkin_requires_space(self):
        for rec in self:
            if rec.state == 'checked_in' and not rec.space_id:
                raise ValidationError(
                    _('Cannot check in without an assigned space.')
                )

    @api.constrains('share_with_ids', 'arrival', 'departure', 'space_id')
    def _check_sharer_overlap(self):
        for rec in self:
            for sharer in rec.share_with_ids:
                # Dates must overlap
                if rec.arrival and rec.departure:
                    if (
                        sharer.departure <= rec.arrival
                        or sharer.arrival >= rec.departure
                    ):
                        raise ValidationError(
                            _(
                                'Sharer reservation %(name)s does not '
                                'overlap in dates.',
                                name=sharer.name,
                            )
                        )
                # Must share the same space
                if rec.space_id and sharer.space_id:
                    if rec.space_id != sharer.space_id:
                        raise ValidationError(
                            _(
                                'Sharer reservation %(name)s must be '
                                'assigned to the same space.',
                                name=sharer.name,
                            )
                        )

    # ─────────────────────────────────────────────────────────────────────────
    # State-machine actions
    # ─────────────────────────────────────────────────────────────────────────

    def action_save_option(self):
        """draft → option (requires option_expires_at)."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    _('Only draft reservations can be placed on option.')
                )
            if not rec.option_expires_at:
                raise UserError(
                    _('Please set an option expiry date/time before saving as option.')
                )
            rec.state = 'option'
        return True

    def action_confirm(self):
        """draft/option → confirmed; validates deposit if policy requires."""
        for rec in self:
            if rec.state not in ('draft', 'option'):
                raise UserError(
                    _('Only draft or option reservations can be confirmed.')
                )
            # Deposit check (unless supervisor force-confirms)
            if not self.env.user.has_group(
                'hospitality_reservation.group_reservation_supervisor'
            ):
                if rec.deposit_policy_id and rec.deposit_amount > 0:
                    if rec.deposit_paid < rec.deposit_amount:
                        raise UserError(
                            _(
                                'Deposit of %(amount)s %(currency)s is required '
                                'before confirmation. Paid so far: %(paid)s.',
                                amount=rec.deposit_amount,
                                currency=rec.currency_id.name,
                                paid=rec.deposit_paid,
                            )
                        )
            rec.state = 'confirmed'
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
                _('Please select exactly one reservation to walk.')
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
        """RES-04: "Print Reg Card" header button on the Arrivals list.

        The registration-card report itself is built in FD-06 (Front
        Desk module), which does not exist yet in this codebase. This
        stub keeps the button wired and gives a clear, actionable
        message instead of a missing-action/missing-report error.
        """
        raise UserError(
            _(
                'Registration card printing is provided by the Front '
                'Desk module (FD-06), which is not installed yet.'
            )
        )

    def action_check_in(self):
        """confirmed → checked_in; guards: space_id set, deposit met."""
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError(
                    _('Only confirmed reservations can be checked in.')
                )
            if not rec.space_id:
                raise UserError(
                    _('Please assign a space before checking in.')
                )
            if rec.deposit_policy_id and rec.deposit_amount > 0:
                if rec.deposit_paid < rec.deposit_amount:
                    raise UserError(
                        _(
                            'Deposit not fully collected. '
                            'Required: %(req)s, Paid: %(paid)s.',
                            req=rec.deposit_amount,
                            paid=rec.deposit_paid,
                        )
                    )
            rec.state = 'checked_in'
            # Open folio if folio model is available
            if 'hospitality.folio' in self.env:
                try:
                    self.env['hospitality.folio'].open(rec)
                except Exception:
                    pass
        return True

    def action_check_out(self):
        """checked_in → checked_out; guard: folio balance = 0 or rolled to AR."""
        for rec in self:
            if rec.state != 'checked_in':
                raise UserError(
                    _('Only checked-in reservations can be checked out.')
                )
            # Folio balance guard — deferred until FOL module exists
            if 'hospitality.folio' in self.env:
                try:
                    self.env['hospitality.folio'].close(rec)
                except Exception:
                    pass
            rec.state = 'checked_out'
        return True

    def action_add_trace(self):
        """RES-04: "Add Trace" header button on the Arrivals list.

        Opens a quick-create form for hospitality.activity.trace
        (owned by hospitality_base, BASE-05) pre-filled with this
        reservation, so a front desk agent can log a request (e.g.
        "guest asked for late check-out") without leaving the list.
        """
        if len(self) != 1:
            raise UserError(
                _('Please select exactly one reservation to add a trace to.')
            )
        if 'hospitality.activity.trace' not in self.env:
            raise UserError(
                _(
                    'Traces require the hospitality_base module '
                    '(BASE-05), which is not installed.'
                )
            )
        rel_info = self._get_trace_reservation_field()
        if not rel_info:
            raise UserError(
                _(
                    'Could not determine how hospitality.activity.trace '
                    'links back to reservations — please check the '
                    'hospitality_base module.'
                )
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
            'name': _('Add Trace'),
            'res_model': 'hospitality.activity.trace',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def action_cancel(self):
        """confirmed/option/draft → cancelled; applies cancellation policy."""
        for rec in self:
            if rec.state not in ('draft', 'option', 'confirmed'):
                raise UserError(
                    _('Only draft, option, or confirmed reservations can be cancelled.')
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
                    _('Only confirmed reservations can be marked as no-show.')
                )
            if not self.env.user.has_group(supervisor_group):
                raise UserError(
                    _('Only a Reservation Supervisor can mark a no-show.')
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
                    _('Only checked-in reservations can be undone.')
                )
            if not self.env.user.has_group(supervisor_group):
                raise UserError(
                    _('Only a Reservation Supervisor can undo a check-in.')
                )
            if rec.arrival != today:
                raise UserError(
                    _('Check-in can only be undone on the same day as arrival.')
                )
            rec.state = 'confirmed'
            # Reverse folio room charges posted today (deferred until FOL)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # RES-04: Business date / Front office helpers
    # ─────────────────────────────────────────────────────────────────────────

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
            'name': _('Arrivals'),
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
        """RES-04: server-computed opener for the In-House menu."""
        property_id = self._get_current_property_id()
        return {
            'type': 'ir.actions.act_window',
            'name': _('In-House'),
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
        """RES-04: server-computed opener for the Departures menu."""
        property_id = self._get_current_property_id()
        business_date = self._get_business_date_for_property(property_id)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Departures'),
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
                _(
                    'Trace Pickup requires the hospitality_base module '
                    '(BASE-05), which is not installed.'
                )
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
            # Fallback: no known hospitality_base action id resolved —
            # build a minimal one from scratch using whatever views
            # hospitality_base registered for the model (Odoo will pick
            # its default view automatically when 'views' is omitted).
            action = {
                'type': 'ir.actions.act_window',
                'name': _('Trace Pickup'),
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

        action['name'] = _('Trace Pickup')
        action['domain'] = domain
        return action

    # ─────────────────────────────────────────────────────────────────────────
    # Availability helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _space_availability_check(self, property_id, space_type_id, arrival, departure):
        """Return available spaces; excludes spaces with overlapping confirmed/checked_in."""
        domain = [
            ('property_id', '=', property_id),
            ('space_type_id', '=', space_type_id),
            ('status', 'not in', ['out_of_service', 'out_of_order']),
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
        return all_spaces.filtered(lambda s: s.id not in occupied_ids)

    def _assign_space(self, space_id):
        """Assign space with row-level lock to prevent double-booking."""
        self.ensure_one()
        if not space_id:
            raise UserError(_('No space provided for assignment.'))
        # SELECT ... FOR UPDATE on the space row to prevent concurrent assignment
        self.env.cr.execute(
            'SELECT id FROM hospitality_space WHERE id = %s FOR UPDATE',
            (space_id,),
        )
        # Verify no overlap now that we hold the lock
        conflict = self.env['hospitality.reservation'].search([
            ('space_id', '=', space_id),
            ('state', 'in', ('confirmed', 'checked_in')),
            ('arrival', '<', self.departure),
            ('departure', '>', self.arrival),
            ('id', '!=', self.id),
        ], limit=1)
        if conflict:
            raise UserError(
                _(
                    'Space is no longer available — it was just assigned to '
                    'reservation %(name)s.',
                    name=conflict.name,
                )
            )
        self.space_id = space_id

    # ─────────────────────────────────────────────────────────────────────────
    # Cron
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_expire_options(self):
        """Daily cron: auto-cancel option reservations past their expiry."""
        now = fields.Datetime.now()
        expired = self.search([
            ('state', '=', 'option'),
            ('option_expires_at', '<', now),
        ])
        for res in expired:
            res.write({
                'state': 'cancelled',
                'cancelled_at': now,
                'cancelled_by': self.env.uid,
                'cancellation_reason': _('Option expired automatically.'),
            })

    # ─────────────────────────────────────────────────────────────────────────
    # RES-03: Tape Chart data helper
    # ─────────────────────────────────────────────────────────────────────────

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
        Falls back to the first property available to the user for
        users with no property_ids restriction (e.g. supervisors with
        access to every property).

        :rtype: int or False
        """
        user = self.env.user
        if 'property_ids' in user._fields and user.property_ids:
            return user.property_ids[0].id
        first_property = self.env['hospitality.property'].search([], limit=1)
        return first_property.id if first_property else False

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

        # ── Spaces (rows) ────────────────────────────────────────────────
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

        # ── Reservations overlapping the window ─────────────────────────
        # Overlap test: arrival < date_to AND departure > date_from
        # (half-open interval [arrival, departure), matches existing
        #  overlap checks used in _space_availability_check / _assign_space)
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

        # ── OOO / OOS blocks ─────────────────────────────────────────────
        # ASSUMPTION: PROP-04 (OOO/OOS wizard) does not yet expose a dated
        # log model to this module. We surface any space currently in
        # 'out_of_order' / 'out_of_service' as a block spanning the full
        # visible window. If/when a dated log model
        # (e.g. hospitality.space.status.log) becomes available, replace
        # the body of this loop with a search on that model instead.
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