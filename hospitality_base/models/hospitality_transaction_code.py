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

_SIGN_INVARIANTS = {
    'payment': 'credit',
    'allowance': 'credit',
    'room': 'debit',
}

class HospitalityTransactionCode(models.Model):
    """Manage transaction codes used for hospitality folio postings."""
    _name = 'hospitality.transaction.code'
    _description = 'Hospitality Transaction Code'
    _order = 'category, code'

    name = fields.Char(string='Name', required=True, translate=True,help='Name of the transaction code.',)
    code = fields.Char(string='Code', size=16, required=True, index=True,
                       help='Unique code used to identify the transaction.',
    )
    category = fields.Selection(
        selection=[
            ('room', 'Room'),
            ('fnb', 'F&B'),
            ('telephone', 'Telephone'),
            ('laundry', 'Laundry'),
            ('other_revenue', 'Other Revenue'),
            ('tax', 'Tax'),
            ('deposit', 'Deposit'),
            ('payment', 'Payment'),
            ('paid_out', 'Paid Out'),
            ('allowance', 'Allowance'),
            ('commission', 'Commission'),
            ('exchange', 'Exchange'),
        ],
        string='Category',
        required=True,
        help='Category that determines the type of hospitality transaction.',
    )
    account_id = fields.Many2one(
        comodel_name='account.account',
        string='GL Account',
        help='General ledger account for posting at folio close.',
    )
    tax_ids = fields.Many2many(
        comodel_name='account.tax',
        string='Taxes',
        help='Taxes applicable to transactions using this transaction code.',
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        help='Leave empty for a global transaction code.',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company to which this transaction code belongs.',
    )
    sign = fields.Selection(
        selection=[
            ('debit', 'Debit'),
            ('credit', 'Credit'),
            ('both', 'Both'),
        ],
        string='Sign',
        required=True,
        default='debit',
        help='Defines whether the transaction is posted as a debit, credit, or either.',
    )
    show_on_folio = fields.Boolean(string='Show on Folio', default=True,
                            help='Indicates whether transactions using this code are displayed on the guest folio.',
    )
    notes = fields.Text(string='Notes',help='Additional notes or instructions for this transaction code.',)
    active = fields.Boolean(string='Active', default=True,
                            help='Indicates whether the transaction code is active and available for use.',
    )

    _code_uniq = models.Constraint(
        'UNIQUE(code, property_id, company_id)',
        'Transaction code must be unique per company and property.',
    )

    # @api.constrains('code', 'property_id','company_id')
    # def _check_code_unique(self):
    #     """Ensure the Transaction code is unique."""
    #     for transaction in self:
    #         if not transaction.code:
    #             continue
    #         duplicate = self.search([
    #             ('code', '=', transaction.code),
    #             ('property_id', '=', transaction.property_id),
    #             ('company_id', '=', transaction.company_id),
    #             ('id', '!=', transaction.id),
    #         ], limit=1)
    #         if duplicate:
    #             raise ValidationError(
    #                 "Transaction code '%s' must be unique per company and property.."
    #                 % transaction.code
    #             )

    @api.constrains('category', 'sign')
    def _check_sign_invariants(self):
        """The transaction codes must have sign invariants if required"""
        for rec in self:
            required_sign = _SIGN_INVARIANTS.get(rec.category)
            if required_sign and rec.sign != required_sign:
                raise ValidationError(
                    "Transaction codes with category '%s' must have "
                    "sign '%s' (got '%s')." % (
                        rec.category, required_sign, rec.sign
                    )
                )
