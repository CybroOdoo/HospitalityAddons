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

class HospitalityPackage(models.Model):
    """
   Defines a bookable package or offer that can be sold to guests. Packages
   bundle multiple inclusions (services, items, or add-ons) at a combined price.
   Packages can be property-specific or global (shared across properties).
   """
    _name = 'hospitality.package'
    _description = 'Hospitality Package'
    _order = 'code'

    name = fields.Char(
        string='Package Name',
        required=True,
        translate=True,
        help="Display name of the package (e.g., 'Romantic Getaway', 'Business Plus').",
    )
    code = fields.Char(
        string='Code',
        size=16,
        required=True,
        index=True,
        help="Unique alphanumeric identifier for the package (e.g., 'ROM-001', 'BIZ-PKG'). "
             "Used for quick reference and filtering.",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        ondelete='cascade',
        index=True,
        help='Leave empty for a global package.',
    )
    inclusion_ids = fields.One2many(
        comodel_name='hospitality.package.inclusion',
        inverse_name='package_id',
        string='Inclusions',
        help="List of items, services, or add-ons included in this package.",
    )
    total_value = fields.Monetary(
        string='Total Value',
        currency_field='currency_id',
        compute='_compute_total_value',
        store=True,
        help="Automatically calculated sum of all inclusion values (qty × unit value).",
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
        help="Currency used for pricing the package and its inclusions.",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="Uncheck to archive the package. Inactive packages are hidden "
             "from selection lists but retain historical data.",
    )
    description = fields.Html(
        string='Description',
        help="Detailed description of the package, including terms, conditions, "
             "and special features. Supports HTML formatting.",
    )
    image = fields.Image(
        string='Image',
        help="Promotional image for the package (e.g., room photo, amenity shot). "
             "Displayed in marketing materials and booking widgets.",
    )

    @api.depends('inclusion_ids', 'inclusion_ids.qty', 'inclusion_ids.value')
    def _compute_total_value(self):
        """Calculate total package value by summing all inclusion line totals."""
        for rec in self:
            rec.total_value = sum(
                line.qty * line.value for line in rec.inclusion_ids
            )

    @api.constrains('code', 'property_id')
    def _check_unique_code_per_property(self):
        """Ensure package code is unique per property."""
        for rec in self:
            duplicate = self.search(
                [('code', '=', rec.code),
                 ('property_id', '=', rec.property_id.id),
                 ('id', '!=', rec.id)], limit=1)
            if duplicate:
                raise ValidationError(
                    "Package code must be unique per property. "
                    f"Code '{rec.code}' is already used."
                )
