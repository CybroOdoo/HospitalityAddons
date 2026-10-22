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
from odoo import fields, models


class HospitalityProperty(models.Model):
    """Adds night audit configuration to hospitality properties."""
    _inherit = 'hospitality.property'

    auto_audit = fields.Boolean(
        string='Auto-Start Night Audit',
        default=False,
        help=(
            'If enabled, the hourly night audit cron will automatically '
            "create and start a night audit run for this property once "
            "local time passes 02:00 on the property's current business "
            'date, provided no run already exists for that date yet.'
        ),
    )

    def _get_audit_tz(self):
        """Best-effort timezone lookup used by the NA-04 auto-start
        cron to decide whether it's "past 02:00 local time" yet.

        GAP: this module's author could not confirm whether
        hospitality.property carries its own timezone field, so this
        defensively probes a couple of plausible field names before
        falling back to the property's company partner timezone, then
        UTC. Replace with a direct field read once the real field
        name (if any) is confirmed.
        """
        self.ensure_one()
        for candidate in ('tz', 'timezone'):
            if candidate in self._fields:
                value = getattr(self, candidate)
                if value:
                    return value
        if self.company_id and self.company_id.partner_id.tz:
            return self.company_id.partner_id.tz
        return 'UTC'