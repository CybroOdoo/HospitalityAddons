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

class HospitalityFloor(models.Model):
    """Manage building floors."""
    _name = 'hospitality.floor'
    _description = 'Floor'
    _order = 'building_id, sequence, code'

    name = fields.Char(
        string='Floor Name',
        required=True,
        translate=True,
        help="Name of the Floor",
    )
    code = fields.Char(
        string='Code',
        size=8,
        required=True,
        index=True,
        help="Code of the Floor",
    )
    building_id = fields.Many2one(
        comodel_name='hospitality.building',
        string='Building',
        required=True,
        ondelete='cascade',
        index=True,
        help="The building to which this Floor belongs to",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        related='building_id.property_id',
        store=True,
        index=True,
        help="The property to which this Floor belongs to",
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Sequence of the Floor",
    )
    space_ids = fields.One2many('hospitality.space', 'floor_id', string='Rooms')
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether the Floor is active or not",
    )

    @api.constrains('code', 'building_id')
    def _check_code_unique_per_building(self):
        """Ensure the floor code is unique per building."""
        for rec in self:
            domain = [
                ('building_id', '=', rec.building_id.id),
                ('code', '=', rec.code),
                ('id', '!=', rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    'Floor code "%s" already exists for this building.' % rec.code
                )

    def action_archive_floor(self):
        """Archive floor."""
        self.write({'active': False})

    def action_unarchive_floor(self):
        """Unarchive floor."""
        self.write({'active': True})
