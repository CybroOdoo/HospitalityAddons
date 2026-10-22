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
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC License
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import logging
from odoo import fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_BLANK_PARTNER_FIELDS = [
    'email', 'phone',
    'street', 'street2', 'city', 'zip',
    'vat', 'birth_date',
]


class GuestRtbfWizard(models.TransientModel):
    """
    Confirmation wizard for the Right-To-Be-Forgotten (RTBF) / anonymisation
    action.  Only hospitality admin users may open and confirm this wizard.

    Flow
    ----
    1. Admin clicks "Execute RTBF" on the guest form.
    2. Odoo opens this wizard (transient) pre-linked to the partner.
    3. Admin ticks confirm_irreversible and clicks action_execute.
    4. action_execute:
       a. Guards: checks confirm_irreversible and admin group membership.
       b. Logs to ir.logging.
       c. Anonymises the partner in-place.
       d. Blanks sensitive ID-document fields (keeps rows for audit trail).
       e. History lines are untouched (accounting integrity).
       f. Returns {type: ir.actions.act_window_close}.
    """

    _name = 'hospitality.guest.rtbf.wizard'
    _description = 'Guest RTBF Anonymisation Wizard'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Guest',
        required=True,
        ondelete='cascade',
        readonly=True,
        help="The guest who will be anonymised.",
    )
    guest_name = fields.Char(
        related='partner_id.name',
        string='Guest Name',
        readonly=True,
        help="The name of the guest.",
    )
    confirm_irreversible = fields.Boolean(
        string='I understand this action is irreversible',
        default=False,
        help="Confirm this action is irreversible.",
    )

    def _check_admin(self):
        """Raise AccessError if the current user is not a hospitality admin."""
        if not self.env.user.has_group('hospitality_guest_profile.group_guest_pii'):
            raise AccessError(
                "Only Hospitality Administrators may execute the RTBF action."
            )

    def action_execute(self):
        """Execute the anonymisation after confirming the irreversible checkbox."""
        self.ensure_one()
        self._check_admin()
        if not self.confirm_irreversible:
            raise UserError(
                "Please tick the confirmation checkbox to proceed. "
                  "This action cannot be undone."
            )
        partner = self.partner_id
        partner_id = partner.id
        self.env['ir.logging'].create({
            'name': 'hospitality.rtbf',
            'type': 'server',
            'level': 'INFO',
            'dbname': self.env.cr.dbname,
            'message': (
                f"RTBF executed on partner id={partner_id} "
                f"by user id={self.env.uid} ({self.env.user.name})"
            ),
            'path': 'hospitality_guest_profile/wizard/guest_rtbf_wizard.py',
            'func': 'action_execute',
            'line': 0,
        })
        anon_vals = {f: False for f in _BLANK_PARTNER_FIELDS}
        anon_vals.update({
            'name': f'Anonymized #{partner_id}',
            'marketing_consent_email': False,
            'marketing_consent_sms': False,
            'rtbf_anonymized_at': fields.Datetime.now(),
        })
        partner.write(anon_vals)
        for doc in partner.id_document_ids:
            doc.write({
                'number': False,
                'scan_front': False,
                'scan_back': False,
            })
        partner.message_post(
            body=(
                f"RTBF anonymisation executed by {self.env.user.name}. "
                "Personal data has been erased."
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        _logger.info(
            "RTBF anonymised partner id=%s by user id=%s",
            partner_id, self.env.uid,
        )
        return {'type': 'ir.actions.act_window_close'}
