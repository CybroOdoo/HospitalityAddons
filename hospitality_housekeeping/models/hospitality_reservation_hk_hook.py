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

from .hospitality_housekeeping_task import RESERVATION_CHECKED_OUT_STATE


class HospitalityReservationHkHook(models.Model):
    """HK-05: real event hook for departure task creation.

    Now that the hospitality_reservation schema is confirmed,
    action_check_out() transitions state to 'checked_out' via a
    plain field write (rec.state = 'checked_out'), which routes
    through write(). Hooking write() here fires
    _create_task_if_missing() immediately on checkout instead of
    waiting for the next _cron_create_departure_tasks() poll (up to
    15 minutes later).

    The 15-minute cron stays in place as a safety net -- e.g. state
    changed by direct ORM write, a script, or an API call that
    doesn't go through this model's write() (it always does, since
    ORM writes all route through write(), but keeping the cron costs
    nothing and covers cases like a restore/import that skips
    business logic). Both routes are idempotent: they share the same
    _create_task_if_missing() dedup check, so a space never gets two
    departure tasks for the same business date.
    """
    _inherit = 'hospitality.reservation'

    def write(self, vals):
        """Create a departure housekeeping task immediately when a
            reservation is checked out, while preserving the standard write
            behavior."""
        checking_out = vals.get('state') == RESERVATION_CHECKED_OUT_STATE
        to_notify = self.filtered(
            lambda r: r.state != RESERVATION_CHECKED_OUT_STATE
        ) if checking_out else self.browse()

        result = super().write(vals)

        if to_notify:
            Task = self.env['hospitality.housekeeping.task']
            for rec in to_notify:
                if rec.space_id and rec.property_id:
                    Task._create_task_if_missing(
                        rec.property_id, rec.space_id, 'departure')

        return result