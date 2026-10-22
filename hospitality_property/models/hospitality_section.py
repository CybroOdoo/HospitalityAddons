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


class HospitalitySection(models.Model):
    """Manage building sections."""
    _name = 'hospitality.section'
    _description = 'Section'
    _order = 'building_id, sequence, code'

    name = fields.Char(
        string='Section Name',
        required=True,
        translate=True,
        help="Name of the section",
    )
    code = fields.Char(
        string='Code',
        size=16,
        help="Code of the section",
    )
    building_id = fields.Many2one(
        comodel_name='hospitality.building',
        string='Building',
        required=True,
        ondelete='cascade',
        index=True,
        help="The building to which this section belongs to",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        related='building_id.property_id',
        store=True,
        index=True,
        help="The property to which this section belongs to",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Sequence of the section",
    )
    description = fields.Text(
        string='Description',
        help="Description of the section",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether the section is active or not",
    )

    @api.constrains('code','building_id')
    def _check_code_unique_per_property(self):
        """Enforce code uniqueness per property (application-level check)."""
        for rec in self:
            domain = [
                ('building_id', '=', rec.building_id.id),
                ('code', '=', rec.code),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    'Section code "%s" already exists for this building.' % rec.code
                )
