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

class HospitalityBuilding(models.Model):
    """Manage property buildings."""
    _name = 'hospitality.building'
    _description = 'Building'
    _inherit = ['hospitality.mixin.property']
    _order = 'property_id, sequence, code'

    name = fields.Char(
        string='Building Name',
        required=True,
        translate=True,
        help="Name of the building.",
    )
    code = fields.Char(
        string='Code',
        size=16,
        required=True,
        index=True,
        help="Code of the building.",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Sequence of the building.",
    )
    floor_ids = fields.One2many(
        comodel_name='hospitality.floor',
        inverse_name='building_id',
        string='Floors',
        help="Floors of the building.",
    )
    section_ids = fields.One2many(
        comodel_name='hospitality.section',
        inverse_name='building_id',
        string='Sections',
        help="Sections of the building.",
    )
    description = fields.Text(
        string='Description',
        help="Description of the building.",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether the building is active or not.",
    )

    @api.constrains('code', 'property_id')
    def _check_code_unique_per_property(self):
        """Ensure the building code is unique per property."""
        for rec in self:
            domain = [
                ('property_id', '=', rec.property_id.id),
                ('code', '=', rec.code),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    'Building code "%s" already exists for this property.' % rec.code
                )

    def action_archive_building(self):
        """Archive building."""
        self.write({'active': False})

    def action_unarchive_building(self):
        """Unarchive building."""
        self.write({'active': True})