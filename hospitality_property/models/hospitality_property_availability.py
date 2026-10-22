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
import logging
from datetime import timedelta
from odoo import api, models

_logger = logging.getLogger(__name__)

_REFRESH_THROTTLE_SECONDS = 1

class HospitalityProperty(models.Model):
    """Extends hospitality.property with PROP-05 availability API."""
    _inherit = 'hospitality.property'

    def _space_availability(self, space_type_id, date_from, date_to):
        """Return daily available counts from the materialized view.

        :param space_type_id: int — ID of ``hospitality.space.type``.
        :param date_from: date — start of range (inclusive).
        :param date_to:   date — end of range (inclusive).
        :returns: list of dicts ``{date: date, available_count: int}``
                  one entry per calendar day in the range.
        :rtype: list[dict]
        """
        self.ensure_one()
        if date_to < date_from:
            return []
        self.env.cr.execute(
            """
            SELECT the_date, available
            FROM   hospitality_space_availability_mv
            WHERE  property_id    = %s
              AND  space_type_id  = %s
              AND  the_date BETWEEN %s AND %s
            ORDER BY the_date
            """,
            (self.id, space_type_id, date_from, date_to),
        )
        rows = {r['the_date']: r['available'] for r in self.env.cr.dictfetchall()}
        result = []
        current = date_from
        while current <= date_to:
            result.append({
                'date': current,
                'available_count': rows.get(current, 0),
            })
            current += timedelta(days=1)
        return result

    def _count_reserved(self, space_type_id, the_date):
        """Phase-1 stub — returns 0.
        Overridden by ``hospitality_reservation`` in Phase 1 to return
        the real confirmed-reservation count for the given type and date.
        :param space_type_id: int — ID of ``hospitality.space.type``.
        :param the_date:      date — the calendar date to check.
        :returns: int — number of confirmed reservations.
        """
        return 0

    @api.model
    def _cron_refresh_availability(self):
        """Refresh the availability MV for every active property.

        Throttled: skips a property if it was refreshed less than
        ``_REFRESH_THROTTLE_SECONDS`` second(s) ago.  Runs at most every
        5 minutes (configured on the ``ir.cron`` record).
        """
        ICP = self.env['ir.config_parameter'].sudo()
        properties = self.search([('active', '=', True)])
        import time
        now = time.time()
        for prop in properties:
            param_key = 'hospitality.avail_last_refresh.%d' % prop.id
            last_str = ICP.get_param(param_key, default='0')
            try:
                last_ts = float(last_str)
            except (ValueError, TypeError):
                last_ts = 0.0
            if now - last_ts < _REFRESH_THROTTLE_SECONDS:
                _logger.debug(
                    'Skipping availability refresh for property %s (throttled)',
                    prop.name,
                )
                continue
            try:
                self.env.cr.execute(
                    'REFRESH MATERIALIZED VIEW CONCURRENTLY '
                    'hospitality_space_availability_mv'
                )
                ICP.set_param(param_key, str(now))
                _logger.info(
                    'Refreshed availability MV for property %s', prop.name
                )
            except Exception:
                _logger.exception(
                    'Failed to refresh availability MV for property %s',
                    prop.name,
                )
