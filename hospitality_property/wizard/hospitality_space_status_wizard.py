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
from odoo.exceptions import ValidationError
from datetime import date

class HospitalitySpaceStatusWizard(models.TransientModel):
    """Wizard to batch-apply OOO or OOS status to multiple spaces.

    Property managers use this to mark rooms as unavailable for maintenance
    or repairs, specifying a reason and date range.
    """
    _name = 'hospitality.space.status.wizard'
    _description = 'Room Status Wizard (OOO/OOS)'

    space_ids = fields.Many2many(
        comodel_name='hospitality.space',
        string='Rooms',
        required=True,
        help="Rooms whose status is to be applied.",
    )
    mode = fields.Selection(
        selection=[
            ('ooo', 'Out of Order'),
            ('oos', 'Out of Service'),
        ],
        string='Mode',
        required=True,
        help="The status to be applied.",
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        help="The reason to be applied.",
    )
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=fields.Date.context_today,
        help="The date from which the room status will be applied.",
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        help="The date to which the room status will be applied.",
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Validate date range: date_from >= today, date_to >= date_from."""
        for rec in self:
            if rec.date_from < date.today():
                raise ValidationError(
                    'Start date cannot be in the past.'
                )
            if rec.date_to < rec.date_from:
                raise ValidationError(
                    'End date must be after or equal to start date.'
                )

    def action_apply(self):
        """Apply OOO/OOS status to all selected spaces."""
        self.ensure_one()
        if not self.space_ids:
            raise ValidationError('Please select at least one room.')
        values = {
            'status': self.mode,
        }
        if self.mode == 'ooo':
            values.update({
                'ooo_reason': self.reason,
                'ooo_from': self.date_from,
                'ooo_to': self.date_to,
            })
        else:
            values.update({
                'oos_reason': self.reason,
                'oos_from': self.date_from,
                'oos_to': self.date_to,
            })
        self.space_ids.write(values)
        return {'type': 'ir.actions.act_window_close'}