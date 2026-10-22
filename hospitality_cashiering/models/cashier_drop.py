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


class HospitalityCashierDrop(models.Model):
    """A witnessed cash drop taken out of the drawer during an open
    shift (e.g. moved to a safe), reducing the cash a cashier is
    physically holding without closing the shift."""
    _name = 'hospitality.cashier.drop'
    _description = 'Hospitality Cashier Shift Drop'
    _order = 'dropped_at desc'

    shift_id = fields.Many2one(
        'hospitality.cashier.shift', string='Cashier Shift',
        required=True, ondelete='cascade', index=True,
        help="The cashier shift from which cash is being dropped. "
             "Drop records are cascade-deleted when their parent shift is deleted.",
    )
    amount = fields.Monetary(
        string='Amount', required=True, currency_field='currency_id',
        help="The total cash amount being removed from the cash drawer "
             "and transferred to a secure location.",
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id.id,
        help="The currency of the cash being dropped. Supports multi-currency "
             "cash handling operations.",
    )
    dropped_at = fields.Datetime(
        string='Dropped At', default=fields.Datetime.now,
        help="Timestamp when the cash drop was performed. Defaults to the "
             "current time when the drop record is created.",
    )
    witness_user_id = fields.Many2one(
        'res.users', string='Witness',
        help="The user who witnessed the cash drop transaction. A witness "
             "provides accountability and helps prevent fraud or discrepancies.",
    )
    notes = fields.Text(string='Notes',
                        help="Additional notes about the cash drop, such as the reason for "
                             "the drop, the destination of the cash (e.g., safe number), "
                             "or any special circumstances.",
                        )