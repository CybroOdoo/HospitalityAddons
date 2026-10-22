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


class HospitalityFrontDeskShift(models.Model):
    """Tracks a front desk agent's shift for a property."""
    _name = 'hospitality.front.desk.shift'
    _description = 'Front Desk Shift'
    _order = 'started_at desc'

    user_id = fields.Many2one(
        'res.users',
        string='Agent',
        required=True,
        default=lambda self: self.env.user.id,
        help='Front desk agent staffing this shift.',
    )
    property_id = fields.Many2one(
        'hospitality.property',
        string='Property',
        required=True,
        help='Property where this shift is being worked.',
    )
    started_at = fields.Datetime(
        string='Started At',
        required=True,
        default=fields.Datetime.now,
        help='Date and time when the shift started.',
    )
    ended_at = fields.Datetime(
        string='Ended At',
        help='Date and time when the shift ended.',
    )
    opening_notes = fields.Text(
        string='Opening Notes',
        help='Notes logged at the start of the shift.',
    )
    closing_notes = fields.Text(
        string='Closing Notes',
        help='Notes logged at the end of the shift.',
    )
    state = fields.Selection(
        [('open', 'Open'), ('closed', 'Closed')],
        string='Status',
        compute='_compute_state',
        store=True,
        help='Current status of the shift (open or closed).',
    )

    @api.depends('ended_at')
    def _compute_state(self):
        """Compute the shift status."""
        for rec in self:
            rec.state = 'closed' if rec.ended_at else 'open'

    def action_close_shift(self):
        """Clock out the current shift, stamping ``ended_at`` to now."""
        for rec in self:
            if not rec.ended_at:
                rec.ended_at = fields.Datetime.now()

    @api.model
    def get_dashboard_data(self, property_id):
        """Return all counters needed by the FD Dashboard OWL widget.

        Every section is wrapped defensively: a missing model/field on a
        dependency (e.g. ``hospitality.reservation`` not yet carrying the
        expected field) degrades that section to a zero count instead of
        breaking the whole dashboard.

        :param property_id: int — ID of the ``hospitality.property``
            currently selected on the front desk.
        :returns: dict with arrivals/in_house/departures counts, available
            rooms by type, occupancy percentage, outstanding AR count, and
            open shifts.
        :rtype: dict
        """
        today = fields.Date.context_today(self)
        result = {
            'property_id': property_id,
            'date': str(today),
            'arrivals_count': 0,
            'in_house_count': 0,
            'departures_count': 0,
            'available_by_type': [],
            'occupancy_pct': 0.0,
            'outstanding_ar_count': 0,
            'open_shifts': [],
        }
        if not property_id:
            return result

        result['arrivals_count'] = self._count_arrivals(property_id, today)
        result['in_house_count'] = self._count_in_house(property_id, today)
        result['departures_count'] = self._count_departures(property_id, today)
        result['available_by_type'] = self._available_by_type(property_id, today)
        result['occupancy_pct'] = self._occupancy_pct(
            property_id, result['available_by_type']
        )
        result['outstanding_ar_count'] = self._outstanding_ar_count(property_id)
        result['open_shifts'] = self._open_shifts(property_id)
        return result

    def _reservation_domain(self, property_id, extra=None):
        """Build the reservation search domain."""
        domain = [('property_id', '=', property_id)]
        if extra:
            domain += extra
        return domain

    def _count_arrivals(self, property_id, today):
        """Count today's confirmed arrivals."""
        Reservation = self.env['hospitality.reservation']
        if 'arrival' not in Reservation._fields:
            return 0
        domain = self._reservation_domain(property_id, [('arrival', '=', today)])
        if 'state' in Reservation._fields:
            domain.append(('state', '=', 'confirmed'))
        return Reservation.search_count(domain)

    def _count_in_house(self, property_id, today):
        """Count checked-in reservations."""
        Reservation = self.env['hospitality.reservation']
        if 'state' not in Reservation._fields:
            return 0
        domain = self._reservation_domain(property_id, [('state', '=', 'checked_in')])
        return Reservation.search_count(domain)

    def _count_departures(self, property_id, today):
        """Count today's checked-in departures."""
        Reservation = self.env['hospitality.reservation']
        if 'departure' not in Reservation._fields:
            return 0
        domain = self._reservation_domain(property_id, [('departure', '=', today)])
        if 'state' in Reservation._fields:
            domain.append(('state', '=', 'checked_in'))
        return Reservation.search_count(domain)

    def _available_by_type(self, property_id, today):
        """Return available rooms grouped by space type."""
        Property = self.env['hospitality.property'].browse(property_id)
        SpaceType = self.env['hospitality.space.type']
        if not Property.exists() or not hasattr(Property, '_space_availability'):
            return []
        space_types = SpaceType.search([('property_id', '=', property_id)])
        data = []
        for space_type in space_types:
            try:
                rows = Property._space_availability(space_type.id, today, today)
            except Exception:
                rows = []
            available = rows[0]['available_count'] if rows else 0
            data.append({
                'space_type_id': space_type.id,
                'name': space_type.name,
                'available': available,
            })
        return data

    def _occupancy_pct(self, property_id, available_by_type):
        """Calculate occupancy percentage."""
        Space = self.env['hospitality.space']
        total = Space.search_count([('property_id', '=', property_id)])
        if not total:
            return 0.0
        available = sum(row['available'] for row in available_by_type)
        occupied = max(total - available, 0)
        return round((occupied / total) * 100.0, 1)

    def _outstanding_ar_count(self, property_id):
        """Count accounts with outstanding balances."""
        ArAccount = self.env.get('hospitality.ar.account')
        if ArAccount is None:
            return 0
        return ArAccount.search_count([
            ('property_id', '=', property_id),
            ('balance', '!=', 0),
        ])

    def _open_shifts(self, property_id):
        """Return all open shifts for the property."""
        shifts = self.search([
            ('property_id', '=', property_id),
            ('ended_at', '=', False),
        ])
        return [{
            'id': shift.id,
            'user': shift.user_id.name,
            'started_at': str(shift.started_at),
        } for shift in shifts]