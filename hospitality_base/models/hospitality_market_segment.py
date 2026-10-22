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

class HospitalityMarketSegment(models.Model):
    """Manage market segments for hospitality properties."""
    _name = 'hospitality.market.segment'
    _description = 'Hospitality Market Segment'
    _order = 'sequence, code'

    name = fields.Char(string='Name', required=True, translate=True,help='Name of the market segment.',)
    code = fields.Char(string='Code', size=16, required=True, index=True,
                       help='Unique code used to identify the market segment.',
    )
    description = fields.Text(string='Description',help='Additional details about the market segment.',)
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        help='Leave empty for a global segment available to all properties.',
    )
    sequence = fields.Integer(string='Sequence', default=10,help='Order in which market segments are displayed.',)
    active = fields.Boolean(string='Active', default=True,help='Indicates whether the market segment is active.',)
    color = fields.Integer(string='Color', default=0,
                           help='Color used to display the market segment in the user interface.',
    )

    @api.constrains('code','property_id')
    def _check_code_unique(self):
        """Ensure the Market segment code is unique."""
        for segment in self:
            if not segment.code:
                continue
            duplicate = self.search([
                ('code', '=', segment.code),
                ('property_id', '=', segment.property_id.id),
                ('id', '!=', segment.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Market segment code '%s' must be unique per property."
                    % segment.code
                )
