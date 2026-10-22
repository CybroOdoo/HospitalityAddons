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
from odoo.exceptions import UserError

class HospitalityContractTerminateWizard(models.TransientModel):
    """Wizard for confirming the termination of a hospitality contract."""
    _name = 'hospitality.contract.terminate.wizard'
    _description = 'Terminate Contract Wizard'

    contract_id = fields.Many2one(
        comodel_name='hospitality.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        help='Contract to be terminated.',
    )
    reason = fields.Text(
        string='Termination Reason',
        required=True,
        help='Reason for terminating the contract.',
    )

    def action_terminate(self):
        """Write termination details to the contract and set state=terminated."""
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError("A termination reason is required.")
        self.contract_id.write({
            'state': 'terminated',
            'termination_reason': self.reason.strip(),
            'terminated_by': self.env.user.id,
            'terminated_at': fields.Datetime.now(),
        })
        return {'type': 'ir.actions.act_window_close'}