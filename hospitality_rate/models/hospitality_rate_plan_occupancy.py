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
from odoo import api,fields, models
from odoo.exceptions import ValidationError


class HospitalityRatePlanOccupancy(models.Model):
    """
    Occupancy Grid Line for Rate Plans.

    Defines specific pricing for adult/children combinations when using
    occupancy_grid pricing mode. Each combination must be unique per plan.
    """
    _name = 'hospitality.rate.plan.occupancy'
    _description = 'Hospitality Rate Plan Occupancy Grid Line'
    _order = 'adults, children'

    plan_id = fields.Many2one(
        comodel_name='hospitality.rate.plan',
        string='Rate Plan',
        required=True,
        ondelete='cascade',
        index=True,
        help="Rate plan this occupancy grid line belongs to. "
    )
    adults = fields.Integer(
        string='Adults',
        required=True,
        help="Number of adults for this occupancy combination (e.g., 1, 2, 3).",
    )
    children = fields.Integer(
        string='Children',
        default=0,
        help="Number of children for this occupancy combination.",
    )
    price = fields.Monetary(
        string='Price',
        required=True,
        currency_field='currency_id',
        help="Total price for this specific adult/children combination.",
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='plan_id.currency_id',
        store=True,
        readonly=True,
        help="Currency inherited from the parent rate plan.",
    )

    @api.constrains('plan_id', 'adults', 'children')
    def _check_unique_occupancy_per_plan(self):
        """Ensure occupancy combination is unique."""
        for record in self:
            duplicate = self.search([
                ('plan_id', '=', record.plan_id.id),
                ('adults', '=', record.adults),
                ('children', '=', record.children),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "This combination already exists."
                )
