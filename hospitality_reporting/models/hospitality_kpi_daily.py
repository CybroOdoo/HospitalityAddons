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
from datetime import datetime, time as dtime

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import _
from odoo.tools.misc import format_date
from odoo.exceptions import UserError


class HospitalityKpiDaily(models.Model):
    """REP-02: one materialized snapshot per (property, business_date),
    written by hospitality_night_audit's step 8 (generate_reports) via
    the override in hospitality_night_audit_run.py.

    All "raw" counters/amounts below (rooms_available, rooms_sold,
    room_revenue, etc.) are plain stored fields written directly by
    _materialize_for_date(). The four derived Monetary/Float fields
    (occupancy_pct, adr, rev_par, total_revenue) are ordinary Odoo
    compute fields with store=True, so they recompute automatically
    whenever _materialize_for_date() writes new raw values — the
    materialization method itself never touches them directly.
    """

    _name = 'hospitality.kpi.daily'
    _description = 'Hospitality Daily KPI Snapshot'
    _order = 'property_id, business_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        index=True,
        help='"<Property> — <Business Date>", used wherever this '
             'record is referenced (breadcrumbs, Many2one widgets, '
             'chatter) instead of a generic record label.',
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        index=True,
        ondelete='cascade',
    )
    business_date = fields.Date(
        string='Business Date',
        required=True,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='property_id.currency_id',
        store=True,
        readonly=True,
    )

    rooms_available = fields.Integer(
        string='Rooms Available',
        help='Total physical (non-virtual) rooms for the property, '
             'including any currently OOO/OOS.',
    )
    rooms_sold = fields.Integer(
        string='Rooms Sold',
        help='Reservations in state checked_in for this property at '
             'the time step 8 of the night audit ran.',
    )
    rooms_ooo = fields.Integer(
        string='Rooms OOO/OOS',
        help='Physical rooms with status ooo or oos.',
    )
    rooms_complimentary = fields.Integer(
        string='Complimentary Rooms',
        help='Checked-in reservations with settlement_method '
             '"complimentary".',
    )

    occupancy_pct = fields.Float(
        string='Occupancy %',
        compute='_compute_occupancy_pct',
        store=True,
        digits=(6, 4),
        help='rooms_sold / (rooms_available - rooms_ooo), as a ratio '
             '(0.5 = 50%), per REP-02 spec.',
    )
    adr = fields.Monetary(
        string='ADR',
        compute='_compute_adr',
        store=True,
        currency_field='currency_id',
        help='Average Daily Rate = room_revenue / rooms_sold.',
    )
    rev_par = fields.Monetary(
        string='RevPAR',
        compute='_compute_revpar',
        store=True,
        currency_field='currency_id',
        help='Revenue Per Available Room = room_revenue / rooms_available.',
    )

    room_revenue = fields.Monetary(
        string='Room Revenue',
        currency_field='currency_id',
        help='Sum of folio line amount (excl. tax) for charge lines '
             'whose transaction code category is "room".',
    )
    fnb_revenue = fields.Monetary(
        string='F&B Revenue',
        currency_field='currency_id',
        help='Sum of folio line amount (excl. tax) for charge lines '
             'whose transaction code category is "fnb".',
    )
    other_revenue = fields.Monetary(
        string='Other Revenue',
        currency_field='currency_id',
        help='Sum of folio line amount (excl. tax) for charge lines '
             'in any other category (telephone, laundry, all/unset).',
    )
    total_revenue = fields.Monetary(
        string='Total Revenue',
        compute='_compute_total_revenue',
        store=True,
        currency_field='currency_id',
        help='room_revenue + fnb_revenue + other_revenue.',
    )

    arrivals = fields.Integer(string='Arrivals')
    departures = fields.Integer(string='Departures')
    no_shows = fields.Integer(string='No-Shows')
    walkins = fields.Integer(string='Walk-Ins')
    cancellations = fields.Integer(
        string='Cancellations',
        help='Reservations cancelled ON this business date '
             '(by cancelled_at), not reservations that were originally '
             'due to arrive on this date.',
    )

    segment_breakdown = fields.Json(
        string='Segment Breakdown (Raw)',
        help='{market segment name: rooms_sold count} for this snapshot. '
             'Raw storage field — see segment_breakdown_display for the '
             'human-readable table shown on the form.',
    )
    source_breakdown = fields.Json(
        string='Source Breakdown (Raw)',
        help='{source code name: rooms_sold count} for this snapshot. '
             'Raw storage field — see source_breakdown_display for the '
             'human-readable table shown on the form.',
    )
    segment_breakdown_display = fields.Html(
        string='Segment Breakdown',
        compute='_compute_breakdown_display',
        sanitize=False,
        help='Read-only table rendering of segment_breakdown, sorted '
             'by rooms sold (descending).',
    )
    source_breakdown_display = fields.Html(
        string='Source Breakdown',
        compute='_compute_breakdown_display',
        sanitize=False,
        help='Read-only table rendering of source_breakdown, sorted '
             'by rooms sold (descending).',
    )

    _property_business_date_uniq = models.Constraint(
        'UNIQUE(property_id, business_date)',
        'A KPI snapshot already exists for this property and business date.',
    )

    @api.depends('rooms_sold', 'rooms_available', 'rooms_ooo')
    def _compute_occupancy_pct(self):
        """
        Compute the occupancy percentage for each KPI snapshot.

        Occupancy is calculated using the number of sold rooms divided by
        the available inventory after excluding out-of-order and
        out-of-service rooms.

        Formula:
            rooms_sold / (rooms_available - rooms_ooo)

        If no rooms are available, the occupancy percentage is set to 0.0.
        """
        for rec in self:
            denom = rec.rooms_available - rec.rooms_ooo
            rec.occupancy_pct = (rec.rooms_sold / denom) if denom else 0.0

    @api.depends('room_revenue', 'rooms_sold')
    def _compute_adr(self):
        """
        Compute the Average Daily Rate (ADR).

        ADR represents the average room revenue earned per sold room.

        Formula:
            room_revenue / rooms_sold

        If no rooms are sold, ADR is set to 0.0.
        """
        for rec in self:
            rec.adr = (rec.room_revenue / rec.rooms_sold) if rec.rooms_sold else 0.0

    @api.depends('room_revenue', 'rooms_available')
    def _compute_revpar(self):
        """
        Compute the Revenue Per Available Room (RevPAR).

        RevPAR measures room revenue generated for each available room,
        regardless of occupancy.

        Formula:
            room_revenue / rooms_available

        If no rooms are available, RevPAR is set to 0.0.
        """
        for rec in self:
            rec.rev_par = (
                rec.room_revenue / rec.rooms_available
            ) if rec.rooms_available else 0.0

    @api.depends('room_revenue', 'fnb_revenue', 'other_revenue')
    def _compute_total_revenue(self):
        """
        Compute the total revenue for the KPI snapshot.

        Total revenue is the sum of room, food and beverage,
        and other operational revenue.

        Formula:
        room_revenue + fnb_revenue + other_revenue
        """
        for rec in self:
            rec.total_revenue = rec.room_revenue + rec.fnb_revenue + rec.other_revenue

    @api.depends('property_id', 'business_date')
    def _compute_name(self):
        """
        Compute the display name of the KPI snapshot.

        The generated name combines the property name and business date
        to provide a meaningful identifier in list views and relational
        fields. If either value is unavailable, a default label is used.
        """
        for rec in self:
            if rec.property_id and rec.business_date:
                rec.name = '%s — %s' % (
                    rec.property_id.name,
                    format_date(rec.env, rec.business_date),
                )
            else:
                rec.name = _('New')

    @api.depends('segment_breakdown', 'source_breakdown')
    def _compute_breakdown_display(self):
        """
        Compute the formatted HTML representation of segment and source
        breakdown data.

        The stored JSON dictionaries are converted into sortable HTML
        tables for display on the KPI form view.
        """
        for rec in self:
            rec.segment_breakdown_display = rec._format_breakdown_html(
                rec.segment_breakdown)
            rec.source_breakdown_display = rec._format_breakdown_html(
                rec.source_breakdown)

    @api.model
    def _format_breakdown_html(self, breakdown):
        """Render a {label: rooms_sold_count} dict as a small sorted
        HTML table instead of raw JSON text. Values are inserted via
        Markup.format(), which auto-escapes them, so segment/source
        names coming from user-entered master data can't inject HTML.
        """
        if not breakdown:
            return Markup('<span class="text-muted">No data</span>')
        rows = Markup('').join(
            Markup('<tr><td>{}</td>'
                   '<td class="text-end ps-3">{}</td></tr>').format(label, count)
            for label, count in sorted(
                breakdown.items(), key=lambda item: item[1], reverse=True)
        )
        header = Markup('<thead><tr><th>{}</th><th class="text-end ps-3">{}</th></tr></thead>').format(
            _('Label'), _('Rooms Sold'))
        return Markup('<table class="table table-sm mb-0">{}<tbody>{}</tbody></table>').format(
            header, rows)

    @api.model
    def _materialize_for_date(self, property_id, business_date):
        """Compute all raw KPI fields for (property_id, business_date)
        and upsert the corresponding hospitality.kpi.daily row.

        Invoked by hospitality_night_audit_run's step-8 override
        (_step_generate_reports). Safe to call more than once for the
        same (property_id, business_date) — updates the existing row
        in place rather than raising the unique constraint.

        :param int property_id: hospitality.property id
        :param date business_date: the audit run's business_date
        :rtype: hospitality.kpi.daily recordset (single record)
        """
        Property = self.env['hospitality.property']
        prop = Property.browse(property_id)
        if not prop.exists():
            raise UserError(
                _('Cannot materialize KPIs: property %s does not exist.')
                % property_id
            )

        Space = self.env['hospitality.space']
        Reservation = self.env['hospitality.reservation']
        Line = self.env['hospitality.folio.line']

        spaces = Space.search([('property_id', '=', property_id)])
        physical_spaces = spaces.filtered(lambda s: not s.is_virtual)
        rooms_available = len(physical_spaces)
        rooms_ooo = len(
            physical_spaces.filtered(lambda s: s.status in ('ooo', 'oos'))
        )

        sold_reservations = Reservation.search([
            ('property_id', '=', property_id),
            ('state', '=', 'checked_in'),
        ])
        rooms_sold = len(sold_reservations)
        rooms_complimentary = len(
            sold_reservations.filtered(
                lambda r: r.settlement_method == 'complimentary'
            )
        )

        arrivals = Reservation.search_count([
            ('property_id', '=', property_id),
            ('arrival', '=', business_date),
        ])
        departures = Reservation.search_count([
            ('property_id', '=', property_id),
            ('departure', '=', business_date),
        ])
        no_shows = Reservation.search_count([
            ('property_id', '=', property_id),
            ('arrival', '=', business_date),
            ('state', '=', 'no_show'),
        ])
        walkins = Reservation.search_count([
            ('property_id', '=', property_id),
            ('arrival', '=', business_date),
            ('is_walkin', '=', True),
        ])
        day_start = datetime.combine(business_date, dtime.min)
        day_end = datetime.combine(business_date, dtime.max)
        cancellations = Reservation.search_count([
            ('property_id', '=', property_id),
            ('state', '=', 'cancelled'),
            ('cancelled_at', '>=', day_start),
            ('cancelled_at', '<=', day_end),
        ])

        charge_lines = Line.search([
            ('property_id', '=', property_id),
            ('business_date', '=', business_date),
            ('transaction_type', '=', 'charge'),
            ('is_void', '=', False),
        ])
        room_lines = charge_lines.filtered(
            lambda l: l.transaction_code_id.category_filter == 'room'
        )
        fnb_lines = charge_lines.filtered(
            lambda l: l.transaction_code_id.category_filter == 'fnb'
        )
        other_lines = charge_lines - room_lines - fnb_lines

        room_revenue = sum(room_lines.mapped('amount'))
        fnb_revenue = sum(fnb_lines.mapped('amount'))
        other_revenue = sum(other_lines.mapped('amount'))

        segment_breakdown = {}
        source_breakdown = {}
        unspecified = _('Unspecified')
        for res in sold_reservations:
            seg_key = res.market_segment_id.name if res.market_segment_id else unspecified
            segment_breakdown[seg_key] = segment_breakdown.get(seg_key, 0) + 1
            src_key = res.source_code_id.name if res.source_code_id else unspecified
            source_breakdown[src_key] = source_breakdown.get(src_key, 0) + 1

        vals = {
            'property_id': property_id,
            'business_date': business_date,
            'rooms_available': rooms_available,
            'rooms_sold': rooms_sold,
            'rooms_ooo': rooms_ooo,
            'rooms_complimentary': rooms_complimentary,
            'room_revenue': room_revenue,
            'fnb_revenue': fnb_revenue,
            'other_revenue': other_revenue,
            'arrivals': arrivals,
            'departures': departures,
            'no_shows': no_shows,
            'walkins': walkins,
            'cancellations': cancellations,
            'segment_breakdown': segment_breakdown,
            'source_breakdown': source_breakdown,
        }

        existing = self.search([
            ('property_id', '=', property_id),
            ('business_date', '=', business_date),
        ], limit=1)
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)

    @api.model
    def _resolve_dashboard_property(self, property_id=False):
        """Resolve the property to show on the Manager Flash dashboard
        when the caller doesn't pin one explicitly.

        Uses the user's current allowed property; with no current
        property, resolves to an empty recordset.

        :param int|False property_id: explicit property to use instead
            of resolving one.
        :rtype: hospitality.property recordset (0 or 1 records)
        """
        if property_id:
            return self.env['hospitality.property'].browse(property_id)
        user = self.env.user
        if 'property_id' in user._fields and user.property_id:
            return user.property_id
        return self.env['hospitality.property'].browse()

    @api.model
    def get_dashboard_properties(self):
        """Properties offered by the Manager Flash property switcher.
        Dashboard access itself is already restricted to Reporting
        User/Manager via ir.model.access.csv and the menu's groups, so
        this simply lists every property the current user can read.

        :rtype: list[dict] — [{'id': int, 'name': str}, ...]
        """
        properties = self.env['hospitality.property'].search([], order='name')
        return [{'id': prop.id, 'name': prop.name} for prop in properties]

    @api.model
    def get_manager_flash_data(self, property_id=False):
        """REP-03: single RPC backing the Manager Flash OWL dashboard.

        Combines two kinds of data:

        * Headline KPIs (occupancy/ADR/RevPAR/room revenue), their
          day-over-day deltas, flow counts (arrivals/departures/
          no-shows/walk-ins), and channel/source mix — all read from
          the latest two hospitality.kpi.daily snapshots for the
          property. These are materialized by night audit step 8, so
          this is what makes the dashboard "show live KPIs immediately
          after a night audit" per the REP-03 acceptance criterion.
        * "Tonight's" in-house count and outstanding balance — computed
          directly and live from hospitality.reservation /
          hospitality.folio, since those move throughout the day
          independent of when the next night audit runs.

        :param int|False property_id: defaults to the current user's
            property via _resolve_dashboard_property().
        :rtype: dict
        """
        prop = self._resolve_dashboard_property(property_id)
        if not prop:
            return {
                'has_data': False,
                'property_id': False,
                'property_name': False,
            }

        snapshots = self.search([
            ('property_id', '=', prop.id),
        ], order='business_date desc', limit=2)
        today_kpi = snapshots[:1]
        prior_kpi = snapshots[1:2]

        def _val(recordset, field):
            return getattr(recordset, field) if recordset else 0.0

        def _delta(field):
            return _val(today_kpi, field) - _val(prior_kpi, field)

        def _mix(recordset, field):
            breakdown = getattr(recordset, field) if recordset else {}
            return [
                {'label': label, 'value': value}
                for label, value in sorted(
                    (breakdown or {}).items(),
                    key=lambda item: item[1], reverse=True)
            ]

        Reservation = self.env['hospitality.reservation']
        Folio = self.env['hospitality.folio']
        in_house = Reservation.search([
            ('property_id', '=', prop.id),
            ('state', '=', 'checked_in'),
        ])
        in_house_balance = 0.0
        if 'balance_due' in Folio._fields:
            in_house_folios = Folio.search([
                ('reservation_id', 'in', in_house.ids),
            ])
            in_house_balance = sum(in_house_folios.mapped('balance_due'))

        return {
            'has_data': bool(today_kpi),
            'property_id': prop.id,
            'property_name': prop.name,
            'currency_symbol': prop.currency_id.symbol or '',
            'business_date': fields.Date.to_string(today_kpi.business_date)
                if today_kpi else False,
            'kpis': {
                'occupancy_pct': _val(today_kpi, 'occupancy_pct'),
                'occupancy_pct_delta': _delta('occupancy_pct'),
                'adr': _val(today_kpi, 'adr'),
                'adr_delta': _delta('adr'),
                'rev_par': _val(today_kpi, 'rev_par'),
                'rev_par_delta': _delta('rev_par'),
                'room_revenue': _val(today_kpi, 'room_revenue'),
                'room_revenue_delta': _delta('room_revenue'),
            },
            'flow': {
                'arrivals': _val(today_kpi, 'arrivals'),
                'departures': _val(today_kpi, 'departures'),
                'no_shows': _val(today_kpi, 'no_shows'),
                'walkins': _val(today_kpi, 'walkins'),
            },
            'in_house': {
                'count': len(in_house),
                'balance': in_house_balance,
            },
            'channel_mix': _mix(today_kpi, 'segment_breakdown'),
            'source_mix': _mix(today_kpi, 'source_breakdown'),
        }
