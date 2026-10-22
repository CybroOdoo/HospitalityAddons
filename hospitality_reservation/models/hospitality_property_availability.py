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
from odoo import models

class HospitalityPropertyAvailability(models.Model):
    """Extend hospitality.property to provide real reservation counts."""
    _inherit = 'hospitality.property'

    def _count_reserved(self, space_type_id, the_date):
        """Return the number of confirmed/checked-in reservations for this
        property that occupy *space_type_id* on *the_date*.

        A reservation occupies a date when:
            arrival <= the_date < departure

        Only states that actually block inventory are counted:
            - confirmed  (guest is expected)
            - checked_in (guest is in-house)

        States that do NOT block inventory are intentionally excluded:
            - draft / option  (tentative, not yet confirmed)
            - checked_out / cancelled / no_show  (space is free again)

        Args:
            space_type_id (int): ID of hospitality.space.type to query.
            the_date (date):     The calendar date to check.

        Returns:
            int: Number of blocking reservations on that date.
        """
        self.ensure_one()
        self.env['hospitality.reservation'].flush_model()
        self.env.cr.execute(
            """
            SELECT COUNT(*)
              FROM hospitality_reservation
             WHERE property_id       = %s
               AND space_type_id     = %s
               AND state             IN ('confirmed', 'checked_in')
               AND arrival           <= %s
               AND departure         >  %s
            """,
            (self.id, space_type_id, the_date, the_date),
        )
        row = self.env.cr.fetchone()
        return row[0] if row else 0

    def _refresh_availability_mv(self):
        """Refresh the hospitality_space_availability_mv materialized view.

        Called after reservation state changes that affect availability
        (confirm, cancel, check-in, check-out).  Delegates to the PROP-05
        method if it exists; silently skips if the MV is not installed yet
        (e.g. during unit tests that only install hospitality_reservation).
        """
        refresh_fn = getattr(
            super(), '_refresh_availability_mv', None
        )
        if callable(refresh_fn):
            refresh_fn()
        else:
            try:
                self.env.cr.execute(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY "
                    "hospitality_space_availability_mv"
                )
            except Exception:
                pass
