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


class HospitalityBeUpsell(models.Model):
    """Add-on/upsell offer presentable to guests during the public
    booking flow (e.g. late checkout, breakfast, spa credit)."""

    _name = 'hospitality.be.upsell'
    _description = 'Booking Engine Upsell'
    _rec_name = 'name'
    _order = 'sequence, name'

    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
    )
    name = fields.Char(string='Name', required=True, translate=True)
    description = fields.Html(string='Description')
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='property_id.currency_id',
        store=True,
        readonly=True,
    )
    price = fields.Monetary(
        string='Price',
        required=True,
        currency_field='currency_id',
    )
    post_to_transaction_code_id = fields.Many2one(
        comodel_name='hospitality.transaction.code',
        string='Post To Transaction Code',
        required=True,
        help='Transaction code this upsell is posted against when '
             'charged to a folio.',
    )
    applies_to_space_type_ids = fields.Many2many(
        comodel_name='hospitality.space.type',
        relation='hospitality_be_upsell_space_type_rel',
        column1='upsell_id',
        column2='space_type_id',
        string='Applies To Room Types',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    image = fields.Image(string='Image')