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
from odoo.tools import _


class HospitalityNightAuditRun(models.Model):
    """REP-02: hook hospitality.kpi.daily materialization onto step 8
    (generate_reports) of the night audit, per the STEP_CHOICES order
    defined in hospitality_night_audit_step.py. hospitality_reporting
    depends on hospitality_night_audit, so this _inherit is safe to
    load in every install.
    """
    _inherit = 'hospitality.night.audit.run'

    def _step_generate_reports(self):
        """
        Extend the night audit report generation step by creating the
        daily KPI snapshot.

        After the standard report generation completes successfully,
        this method materializes the property's daily KPI record for
        the current business date. If KPI generation fails, the night
        audit step is marked as failed and the corresponding error is
        appended to the returned message.

        :return: A tuple containing the step status and result message.
        :rtype: tuple[str, str]
        """
        status, message = super()._step_generate_reports()

        if status == 'failed':
            return (status, message)

        try:
            kpi = self.env['hospitality.kpi.daily']._materialize_for_date(
                self.property_id.id, self.business_date,
            )
        except Exception as exc:
            combined = _(
                '%(report_msg)s KPI materialization failed: %(err)s'
            ) % {'report_msg': message or '', 'err': exc}
            return ('failed', combined)

        extra = _(
            'KPI snapshot recorded — %(occ).1f%% occupancy, '
            '%(rev)s total revenue.'
        ) % {
            'occ': kpi.occupancy_pct * 100.0,
            'rev': kpi.total_revenue,
        }
        combined_message = ('%s %s' % (message, extra)).strip() if message else extra
        return (status, combined_message)