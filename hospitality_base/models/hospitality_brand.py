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

class HospitalityBrand(models.Model):
    """Manage hospitality brands and their hierarchical relationships."""
    _name = 'hospitality.brand'
    _description = 'Hospitality Brand'
    _order = 'sequence, name'

    name = fields.Char(
        string='Brand Name',
        required=True,
        translate=True,
        help="Name of the brand.",
    )
    code = fields.Char(
        string='Code',
        size=16,
        required=True,
        help="Brand Code",
    )
    parent_id = fields.Many2one(
        comodel_name='hospitality.brand',
        string='Parent Brand',
        index=True,
        ondelete='restrict',
        help="Parent Brand ID",
    )
    child_ids = fields.One2many(
        comodel_name='hospitality.brand',
        inverse_name='parent_id',
        string='Child Brands',
        help="Child Brand IDs",
    )
    property_ids = fields.One2many(
        comodel_name='hospitality.property',
        inverse_name='brand_id',
        string='Properties',
        help="Properties associated with each brand"
    )
    property_count = fields.Integer(
        # Not 'Properties': property_ids already carries that label, and two
        # fields on one model sharing a label is ambiguous in the UI and in
        # exports - Odoo warns about it at load.
        string='Property Count',
        compute='_compute_property_count',
        help="The total number of properties associated with each brand.",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="The sequence in which each brand will be displayed.",
    )
    description = fields.Text(string='Description',help="Description of the brand.")
    active = fields.Boolean(string='Active', default=True,help="Whether or not the brand is active.")

    @api.constrains('code')
    def _check_code_unique(self):
        """Ensure the brand code is unique."""
        for brand in self:
            if not brand.code:
                continue
            duplicate = self.search([
                ('code', '=', brand.code),
                ('id', '!=', brand.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Brand code '%s' must be unique across all brands."
                    % brand.code
                )

    @api.depends('property_ids')
    def _compute_property_count(self):
        """Calculate the total number of properties associated with each brand."""
        for brand in self:
            brand.property_count = len(brand.property_ids)

    @api.constrains('parent_id')
    def _check_no_cycle(self):
        """Prevent circular parent-child relationships in brand hierarchy."""
        for brand in self:
            current = brand.parent_id
            visited = {brand.id}
            while current:
                if current.id in visited:
                    raise ValidationError(
                        "A cycle was detected in the brand hierarchy. "
                        "A brand cannot be its own ancestor."
                    )
                visited.add(current.id)
                current = current.parent_id
