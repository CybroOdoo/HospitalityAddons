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

class HospitalitySpaceFeature(models.Model):
    """Amenity / feature catalogue entry (e.g. WIFI, BALCONY, BATHTUB).

    Instances are property-agnostic — a single catalogue is shared across
    all properties.  Individual space types subscribe to features through
    the Many2many on ``hospitality.space.type``.
    """
    _name = 'hospitality.space.feature'
    _description = 'Room Feature'
    _order = 'sequence, name'

    name = fields.Char(
        string='Feature Name',
        required=True,
        translate=True,
        help="Name of the feature",
    )
    code = fields.Char(
        string='Code',
        size=24,
        required=True,
        index=True,
        help="Unique code for this feature",
    )
    icon = fields.Char(
        string='Icon',
        help='Font Awesome class name, e.g. fa-wifi',
    )
    description = fields.Text(
        string='Description',
        help='Description of the feature',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help="Sequence number of the feature",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Whether the feature is active or not.",
    )

    @api.constrains('code')
    def _check_code_unique(self):
        """Python-level uniqueness check — fires before DB flush."""
        for rec in self:
            domain = [('code', '=', rec.code), ('id', '!=', rec.id)]
            if self.search_count(domain):
                raise ValidationError(
                    'Feature code "%s" already exists. '
                    'Feature codes must be globally unique.' % rec.code
                )

    def action_archive_space_feature(self):
        """Archive space feature."""
        self.write({'active': False})

    def action_unarchive_space_feature(self):
        """Unarchive space feature."""
        self.write({'active': True})
