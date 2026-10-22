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


class HospitalityWorkOrderPart(models.Model):
    """Stores parts and materials consumed by a maintenance work order.
    Each record represents a product used during maintenance,
    including the quantity consumed and its associated cost,
    contributing to the total work order cost.
    """
    _name = 'hospitality.work.order.part'
    _description = 'Hospitality Work Order Part / Material Used'

    work_order_id = fields.Many2one(
        'hospitality.work.order', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    qty = fields.Float(required=True, default=1.0)
    currency_id = fields.Many2one(
        related='work_order_id.currency_id', store=True, readonly=True)
    cost = fields.Monetary(required=True, currency_field='currency_id')