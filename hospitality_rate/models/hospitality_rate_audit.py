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

class HospitalityRateAudit(models.Model):
    """
    Audit log tracking changes to rate-related records.
    Captures before/after states, user, timestamp, and reason for changes.
    """
    _name = 'hospitality.rate.audit'
    _description = 'Hospitality Rate Audit Log'
    _order = 'changed_at desc'

    name = fields.Char(
        string='Description',
        compute='_compute_name',
        store=True,
        help="Auto-generated description: Model name and record ID.",
    )
    rate_code_id = fields.Many2one(
        comodel_name='hospitality.rate.code',
        string='Rate Code',
        ondelete='cascade',
        required=True,
        index=True,
        help="Rate code being audited. Deleting the rate code removes its audit logs.",
    )
    model = fields.Char(
        string='Model',
        required=True,
        help="Technical name of the model being audited (e.g., 'hospitality.rate.line').",
    )
    record_id = fields.Integer(
        string='Record ID',
        required=True,
        help="Database ID of the audited record.",
    )
    changed_by = fields.Many2one(
        comodel_name='res.users',
        string='Changed By',
        required=True,
        default=lambda self: self.env.user,
        help="User who performed the change.",
    )
    changed_at = fields.Datetime(
        string='Changed At',
        default=fields.Datetime.now,
        readonly=True,
        help="Timestamp of the change.",
    )
    before_json = fields.Json(
        string='Before (JSON)',
        help="Snapshot of the record's state before the change, in JSON format.",
    )
    after_json = fields.Json(
        string='After (JSON)',
        help="Snapshot of the record's state after the change, in JSON format.",
    )
    reason = fields.Text(
        string='Reason',
        help="Optional explanation for why the change was made.",
    )

    @api.depends('model', 'record_id')
    def _compute_name(self):
        """Generate description from model and record ID."""
        for rec in self:
            rec.name = f"Audit: {rec.model} [{rec.record_id}]"
