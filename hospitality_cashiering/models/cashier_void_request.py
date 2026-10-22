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
from odoo.tools import _
from odoo.exceptions import AccessError, UserError


class HospitalityVoidRequest(models.Model):
    """Supervisor approval workflow for voiding a posted folio line.

    A cashier raises a request against a specific hospitality.folio.line;
    a Cashier Supervisor either approves it (which executes the actual
    void via hospitality.folio._void_line()) or rejects it (leaving the
    original line untouched).
    """
    _name = 'hospitality.void.request'
    _inherit = ['mail.thread']
    _description = 'Hospitality Folio Line Void Request'
    _order = 'requested_at desc'
    _rec_name = 'folio_id'

    folio_line_id = fields.Many2one(
        'hospitality.folio.line', string='Folio Line', required=True,
        ondelete='restrict', index=True, tracking=True,
        help="The folio line being requested for void. This line must "
             "be valid and not already voided before approval.",
    )

    folio_id = fields.Many2one(
        related='folio_line_id.folio_id', string='Folio', store=True,
        readonly=True,help="The folio containing the line being requested for void.",)
    property_id = fields.Many2one(
        related='folio_line_id.folio_id.property_id', string='Property',
        store=True, readonly=True,help="The property where the void request originates.",)
    transaction_code_id = fields.Many2one(
        related='folio_line_id.transaction_code_id',
        string='Transaction Code', store=True, readonly=True,
        help="The transaction code of the folio line being voided.",
    )
    currency_id = fields.Many2one(
        related='folio_line_id.currency_id', string='Currency',
        store=True, readonly=True,help="The currency of the amount being voided.",)
    amount = fields.Monetary(
        related='folio_line_id.amount_total', string='Amount',
        currency_field='currency_id', store=True, readonly=True,
        help="The monetary amount of the folio line being requested for void.",
    )

    requested_by = fields.Many2one(
        'res.users', string='Requested By', required=True,
        default=lambda self: self.env.user,        help="The cashier who submitted the void request.",)
    requested_at = fields.Datetime(
        string='Requested At', required=True, default=fields.Datetime.now,
        help="Timestamp when the void request was submitted.",
    )
    approved_by = fields.Many2one(
        'res.users', string='Approved By', copy=False, readonly=True,
        help="The supervisor who approved or rejected this request.",
    )
    approved_at = fields.Datetime(
        string='Approved At', copy=False, readonly=True,
        help="Timestamp when the request was approved or rejected.",
    )
    reason = fields.Text(string='Reason', required=True,
                         help="Detailed explanation for why the void is being requested. "
                              "This provides audit trail and justification for the void.",
                         )
    state = fields.Selection(
        [('requested', 'Requested'), ('approved', 'Approved'),
         ('rejected', 'Rejected')],
        string='Status', required=True, default='requested', tracking=True,
        copy=False,help="Current state of the void request: Requested (awaiting review), "
             "Approved (void executed), or Rejected (void denied).",)

    @api.constrains('folio_line_id', 'state')
    def _check_single_active_request(self):
        """Defensive guard (not in the literal spec): a folio line
        shouldn't have more than one open 'requested' void request at a
        time, to avoid two supervisors approving/rejecting the same
        line independently."""
        for request in self:
            if request.state != 'requested':
                continue
            duplicate = self.search([
                ('id', '!=', request.id),
                ('folio_line_id', '=', request.folio_line_id.id),
                ('state', '=', 'requested'),
            ], limit=1)
            if duplicate:
                raise UserError(_(
                    "Folio line %(line)s already has an open void "
                    "request (#%(other)s).",
                    line=request.folio_line_id.id, other=duplicate.id))

    def action_approve(self):
        """Supervisor only: approve the request and execute the void on
        the folio.

        NOTE: hospitality.folio._void_line() enforces its own
        has_group('hospitality_folio.group_folio_supervisor') check,
        independent of the gate below. To let a Cashier Supervisor
        actually execute the void they just approved, this module's
        security data (security/cashier_security.xml) makes
        group_cashier_supervisor imply
        hospitality_folio.group_folio_supervisor. Flag to the product
        owner if Cashier Supervisor and Folio Supervisor are meant to
        stay fully separate roles — remove that implied_ids line to
        decouple them again.
        """
        if not self.env.user.has_group(
                'hospitality_cashiering.group_cashier_supervisor'):
            raise AccessError(_(
                "Only a Cashier Supervisor can approve void requests."))
        for request in self:
            if request.state != 'requested':
                raise UserError(_(
                    "Only requested void requests can be approved "
                    "(request %(id)s is %(state)s).",
                    id=request.id, state=request.state))
            line = request.folio_line_id
            if line.is_void:
                raise UserError(_(
                    "Folio line %(id)s is already voided.", id=line.id))
            line.folio_id._void_line(line.id, reason=request.reason)
            request.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
            })
        return True

    def action_reject(self):
        """Supervisor only: reject the request, leaving the original
        folio line untouched."""
        if not self.env.user.has_group(
                'hospitality_cashiering.group_cashier_supervisor'):
            raise AccessError(_(
                "Only a Cashier Supervisor can reject void requests."))
        for request in self:
            if request.state != 'requested':
                raise UserError(_(
                    "Only requested void requests can be rejected "
                    "(request %(id)s is %(state)s).",
                    id=request.id, state=request.state))
            request.write({
                'state': 'rejected',
                'approved_by': self.env.user.id,
                'approved_at': fields.Datetime.now(),
            })
        return True