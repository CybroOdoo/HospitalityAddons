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

class HospitalityDietary(models.Model):
    """
    Dietary restriction lookup — Many2many tag on res.partner.
    Each record carries a short code used in integrations / exports and
    an optional icon glyph for display in kanban cards or PDF folios.
    """
    _name        = 'hospitality.dietary'
    _description = 'Dietary Restriction'
    _order       = 'name'

    name = fields.Char(
        string='Dietary Restriction',
        required=True,
        translate=True,
        help='E.g. Vegan, Gluten-Free, Halal, Nut Allergy',
    )
    code = fields.Char(
        string='Code',
        size=24,
        required=True,
        index=True,
        help='Short machine-readable identifier, e.g. GF, VEGAN.',
    )
    description = fields.Text(string='Description',help="A short description of the dietary restriction.")
    icon = fields.Char(
        string='Icon',
        help='Font Awesome class or Unicode glyph, e.g. fa-leaf.',
    )
    active = fields.Boolean(string="Active",default=True,help="Whether or not the dietary restriction is active.")

    @api.constrains('code')
    def _check_code_unique(self):
        """Ensure the dietary restriction code is unique."""
        for diet in self:
            if not diet.code:
                continue
            duplicate = self.search([
                ('code', '=', diet.code),
                ('id', '!=', diet.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Dietary restriction code '%s' must be unique across all records."
                    % diet.code
                )
