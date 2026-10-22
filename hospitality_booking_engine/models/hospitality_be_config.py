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


class HospitalityBeConfig(models.Model):
    """Look-and-feel and offer settings for a property's public booking
    engine. Exactly one configuration record is allowed per property."""
    _name = 'hospitality.be.config'
    _description = 'Booking Engine Configuration'
    _rec_name = 'property_id'

    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        ondelete='cascade',
    )
    theme = fields.Selection(
        selection=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('brand', 'Brand'),
        ],
        string='Theme',
        default='light',
        required=True,
    )
    primary_color = fields.Char(
        string='Primary Color',
        help='Hex color code used for the booking engine theme, '
             'e.g. #71639E.',
    )
    hero_image = fields.Image(string='Hero Image')
    currency_ids = fields.Many2many(
        comodel_name='res.currency',
        relation='hospitality_be_config_currency_rel',
        column1='config_id',
        column2='currency_id',
        string='Accepted Currencies',
    )
    language_ids = fields.Many2many(
        comodel_name='res.lang',
        relation='hospitality_be_config_lang_rel',
        column1='config_id',
        column2='lang_id',
        string='Languages',
    )
    default_los = fields.Integer(
        string='Default Length of Stay',
        default=2,
        help='Default number of nights pre-selected in the booking '
             'engine search.',
    )
    max_los = fields.Integer(
        string='Maximum Length of Stay',
        default=14,
        help='Maximum number of nights a guest may book in a single '
             'reservation through the booking engine.',
    )
    show_room_photos = fields.Boolean(string='Show Room Photos', default=True)
    show_amenities = fields.Boolean(string='Show Amenities', default=True)
    allow_promo_code = fields.Boolean(string='Allow Promo Code', default=True)
    payment_acquirer_ids = fields.Many2many(
        comodel_name='payment.provider',
        relation='hospitality_be_config_provider_rel',
        column1='config_id',
        column2='provider_id',
        string='Payment Providers',
    )
    tax_inclusive_display = fields.Boolean(
        string='Tax-Inclusive Display',
        default=False,
        help='Display rates inclusive of taxes on the booking engine.',
    )

    _property_unique = models.Constraint(
        'unique(property_id)',
        'Only one Booking Engine configuration is allowed per property.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Pre-check uniqueness before the INSERT is ever issued.

        The SQL unique constraint above is immediate, so a duplicate
        property_id fails at the INSERT itself, during ORM flush —
        which happens *before* @api.constrains methods run. Letting
        that happen surfaces a raw psycopg2.UniqueViolation instead of
        a clean ValidationError (and aborts the transaction). Checking
        here avoids ever issuing the offending INSERT."""
        for vals in vals_list:
            property_id = vals.get('property_id')
            if property_id and self.search_count(
                [('property_id', '=', property_id)]
            ):
                raise ValidationError(
                    "A Booking Engine configuration already exists for "
                    "this property."
                )
        return super().create(vals_list)

    @api.constrains('property_id')
    def _check_property_unique(self):
        """Backstop for paths that don't go through create() above —
        e.g. write() changing property_id to collide with an existing
        config. Note: like create(), a write() collision also risks
        hitting the SQL constraint before this runs; this remains a
        best-effort second layer, not the primary guard."""
        for config in self:
            duplicate = self.search_count([
                ('property_id', '=', config.property_id.id),
                ('id', '!=', config.id),
            ])
            if duplicate:
                raise ValidationError(
                    f"A Booking Engine configuration already exists for "
                    f"property '{config.property_id.display_name}'."
                )