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
"""Read-only data behind the app drawer's stats column.

Nothing here writes, and no other module is modified. Every model is
reached through ``env.get`` so the theme runs with only
``hospitality_base`` present.

If no property resolves, or the models the figures come from are not
installed, ``stats`` comes back empty and the drawer drops the column
entirely rather than showing zeros that read as real counts.

All counts are taken against the property's BUSINESS DATE, not the
system date. The two diverge whenever night audit has not yet rolled the
date forward - the normal state of a hotel after midnight - and the
drawer shows the business date, so its figures have to agree with it.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Space statuses meaning "needs housekeeping attention".
_DIRTY_STATUSES = ('vacant_dirty', 'occupied_dirty', 'pickup')

# Space statuses meaning the room is sold tonight.
_OCCUPIED_STATUSES = ('occupied_clean', 'occupied_dirty')


class HospitalityThemeHome(models.AbstractModel):
    """Aggregator behind the theme's app drawer."""

    _name = 'hospitality.theme.home'
    _description = 'Hospitality Theme Home Data'

    @api.model
    def get_home_data(self):
        """Everything the drawer's left column renders."""
        prop = self._resolve_property()
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())

        data = {
            'user_name': self.env.user.name,
            'greeting': self._greeting(now.hour),
            'date_label': self._date_label(now),
            'time_label': now.strftime('%H:%M'),
            # Minutes since midnight in the USER'S timezone. The drawer
            # ticks its clock forward from this rather than reading the
            # browser's own clock, which would disagree with date_label
            # whenever the two timezones differ.
            'minutes_of_day': now.hour * 60 + now.minute,
            'property_name': prop.display_name if prop else '',
            'business_date': '',
            'stats': [],
        }
        if not prop:
            return data

        business_date = (
            prop.business_date
            if 'business_date' in prop._fields and prop.business_date
            else fields.Date.context_today(self)
        )
        data['business_date'] = business_date.strftime('%d %b %Y').upper()
        data['stats'] = self._stats(prop, business_date)
        return data

    @api.model
    def get_business_date(self):
        """Just the business date, for the navbar systray.

        Deliberately separate from get_home_data: the systray loads on
        every backend page and must not pay for the occupancy and
        reservation counts the drawer needs.
        """
        prop = self._resolve_property()
        if not prop or 'business_date' not in prop._fields \
                or not prop.business_date:
            return {'business_date': ''}
        return {
            'business_date': prop.business_date.strftime('%d %b %Y').upper(),
        }

    # ──────────────────────────────────────────────────────────────────
    #  Stats
    # ──────────────────────────────────────────────────────────────────

    def _stats(self, prop, business_date):
        """The four panels, in the order the design lays them out.

        A panel whose source model is unavailable is left out rather
        than shown as zero.
        """
        stats = []
        rooms = self._room_counts(prop)

        if rooms is not None:
            total, occupied, dirty = rooms
            pct = round(100.0 * occupied / total) if total else 0
            stats.append({
                'key': 'occupancy', 'label': 'Occupancy',
                'value': '%d%%' % pct,
                'sub': '%d of %d rooms' % (occupied, total),
            })

        flow = self._reservation_flow(prop, business_date)
        if flow is not None:
            arrivals, arr_pending, departures, dep_pending = flow
            stats.append({
                'key': 'arrivals', 'label': 'Arrivals',
                'value': str(arrivals), 'sub': '%d pending' % arr_pending,
            })
            stats.append({
                'key': 'departures', 'label': 'Departures',
                'value': str(departures), 'sub': '%d pending' % dep_pending,
            })

        if rooms is not None:
            stats.append({
                'key': 'to_clean', 'label': 'Rooms to clean',
                'value': str(rooms[2]), 'sub': self._check_in_label(prop),
            })
        return stats

    def _room_counts(self, prop):
        """(total, occupied, dirty) or None when spaces are unavailable."""
        Space = self.env.get('hospitality.space')
        if Space is None or 'status' not in Space._fields:
            return None
        try:
            groups = Space._read_group(
                [('property_id', '=', prop.id)],
                groupby=['status'], aggregates=['__count'],
            )
        except Exception:
            _logger.debug('Theme: space read_group failed', exc_info=True)
            return None
        counts = {status: count for status, count in groups}
        if not counts:
            return None
        return (sum(counts.values()),
                sum(counts.get(s, 0) for s in _OCCUPIED_STATUSES),
                sum(counts.get(s, 0) for s in _DIRTY_STATUSES))

    def _reservation_flow(self, prop, business_date):
        """(arrivals, pending, departures, pending) for the business date."""
        Reservation = self.env.get('hospitality.reservation')
        if Reservation is None or 'arrival' not in Reservation._fields:
            return None
        base = [('property_id', '=', prop.id)]
        try:
            arr_in = Reservation.search_count(
                base + [('arrival', '=', business_date),
                        ('state', '=', 'checked_in')])
            arr_pending = Reservation.search_count(
                base + [('arrival', '=', business_date),
                        ('state', '=', 'confirmed')])
            dep_done = Reservation.search_count(
                base + [('departure', '=', business_date),
                        ('state', '=', 'checked_out')])
            dep_pending = Reservation.search_count(
                base + [('departure', '=', business_date),
                        ('state', '=', 'checked_in')])
        except Exception:
            _logger.debug('Theme: reservation counts failed', exc_info=True)
            return None
        return (arr_in + arr_pending, arr_pending,
                dep_done + dep_pending, dep_pending)

    def _check_in_label(self, prop):
        """"before 14:00", from the property's default check-in time."""
        field = 'default_check_in_time'
        if field in prop._fields and prop[field]:
            value = prop[field]
            hours = int(value)
            minutes = int(round((value - hours) * 60))
            if minutes == 60:
                hours, minutes = hours + 1, 0
            return 'before %02d:%02d' % (hours % 24, minutes)
        return 'today'

    # ──────────────────────────────────────────────────────────────────
    #  Context
    # ──────────────────────────────────────────────────────────────────

    def _resolve_property(self):
        """The user's property, else the first one they can read."""
        Property = self.env.get('hospitality.property')
        if Property is None:
            return None
        user = self.env.user
        for field in ('property_id', 'default_property_id'):
            if field in user._fields and user[field]:
                return user[field]
        return Property.search([], limit=1) or None

    @staticmethod
    def _greeting(hour):
        if hour < 12:
            return 'Good morning'
        if hour < 17:
            return 'Good afternoon'
        return 'Good evening'

    @staticmethod
    def _date_label(now):
        """"Tuesday, 13 October" - no year, matching the design."""
        return '%s, %d %s' % (now.strftime('%A'), now.day, now.strftime('%B'))
