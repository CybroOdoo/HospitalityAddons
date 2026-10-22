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
from odoo import fields, models

class HospitalityPackageInclusion(models.Model):
    """
    Line item within a package. Defines a service/product with quantity,
    value, and posting schedule. Aggregated to form the complete package.
    """
    _name = 'hospitality.package.inclusion'
    _description = 'Hospitality Package Inclusion'
    _order = 'package_id, id'

    package_id = fields.Many2one(
        comodel_name='hospitality.package',
        string='Package',
        required=True,
        ondelete='cascade',
        index=True,
        help="Parent package. Deletion cascades to this inclusion.",
    )
    transaction_code_id = fields.Many2one(
        comodel_name='hospitality.transaction.code',
        string='Transaction Code',
        required=True,
        ondelete='restrict',
        help="Service/product/fee being included (e.g., 'Room Rate', 'Breakfast').",
    )
    qty = fields.Float(
        string='Quantity',
        default=1.0,
        help="Number of units. Total = qty × value.",
    )
    value = fields.Monetary(
        string='Value',
        required=True,
        currency_field='currency_id',
        help="Unit price for this inclusion.",
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='package_id.currency_id',
        store=True,
        readonly=True,
        help="Inherited from parent package.",
    )
    posting_rhythm = fields.Selection(
        selection=[
            ('per_stay', 'Per Stay'),
            ('per_night', 'Per Night'),
            ('per_pax_per_night', 'Per Pax Per Night'),
            ('on_arrival', 'On Arrival'),
        ],
        string='Posting Rhythm',
        required=True,
        default='per_night',
        help="Charge frequency: per stay, per night, per guest per night, or on arrival.",
    )
    notes = fields.Char(
        string='Notes',
        help="Additional notes or special instructions.",
    )
