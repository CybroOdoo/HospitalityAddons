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


class HospitalityCashierAmount(models.Model):
    """A single currency line of a cashier shift's opening or closing
    drawer count. A shift can hold several of these (one per currency)
    to support a multi-currency drawer."""
    _name = 'hospitality.cashier.amount'
    _description = 'Hospitality Cashier Shift Drawer Amount'
    _order = 'kind, currency_id'

    shift_id = fields.Many2one(
        'hospitality.cashier.shift', string='Cashier Shift',
        required=True, ondelete='cascade', index=True,
        help="The cashier shift that this drawer amount belongs to. "
             "Amount lines are cascade-deleted when their parent shift is deleted.",
    )
    kind = fields.Selection(
        [('opening', 'Opening'), ('closing', 'Closing')],
        string='Kind', required=True,
        help="Indicates whether this amount line represents the drawer "
             "count at the start of the shift (Opening) or at the end "
             "of the shift (Closing).",
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id.id,
        help="The currency of this amount line. Each shift can have multiple "
             "amount lines with different currencies to support multi-currency "
             "cash drawers.",
    )
    amount = fields.Monetary(
        string='Amount', required=True, currency_field='currency_id',
        help="The total cash amount counted in this currency for the drawer, "
             "either at shift opening or closing.",
    )

    @api.constrains('shift_id', 'kind','currency_id')
    def _check_currency_unique(self):
        """Ensure only one amount line per currency is allowed for each kind."""
        for record in self:
            duplicate = self.search([
                ('shift_id', '=', record.shift_id.id),
                ('kind', '=', record.kind),
                ('currency_id', '=', record.currency_id.id),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    "Only one amount line per currency is allowed for each kind "
                    "'(opening/closing) on a given cashier shift."
                )