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
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api,fields, models
from odoo.exceptions import ValidationError

class HospitalityGuestPreference(models.Model):
    """
    Guest preference lookup — Many2many tag on res.partner.
    Preferences are categorised so the UI can group them meaningfully
    (room attributes vs. F&B requests vs. custom items).
    """
    _name        = 'hospitality.guest.preference'
    _description = 'Guest Preference'
    _order       = 'category, name'

    name = fields.Char(
        string='Preference',
        required=True,
        translate=True,
        help='E.g. High Floor, Feather Pillow, Late Housekeeping',
    )
    code = fields.Char(
        string='Code',
        size=24,
        required=True,
        index=True,
        help='Short machine-readable identifier, e.g. HIGH_FLOOR.',
    )
    category = fields.Selection(
        selection=[
            ('room_attribute', 'Room Attribute'),
            ('service',        'Service'),
            ('fnb',            'Food & Beverage'),
            ('custom',         'Custom'),
        ],
        string='Category',
        required=True,
        default='room_attribute',
        help="Guest preference category.",
    )
    description = fields.Text(string='Description',help="Short description of the preference.")
    active = fields.Boolean(default=True,help="Whether the preference is active or not.")

    @api.constrains('code')
    def _check_code_unique(self):
        """Ensure the preference code is unique."""
        for preference in self:
            if not preference.code:
                continue
            duplicate = self.search([
                ('code', '=', preference.code),
                ('id', '!=', preference.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Preference code '%s' must be unique across all records."
                    % preference.code
                )
