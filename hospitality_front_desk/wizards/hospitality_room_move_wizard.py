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
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HospitalityRoomMoveWizard(models.TransientModel):
    """FD-05 — Move an in-house guest from their current space to a new one.

    The move is performed atomically: both space rows are locked, the
    reservation's space is repointed, and both spaces have their
    housekeeping status updated in the same transaction.
    """

    _name = 'hospitality.room.move.wizard'
    _description = 'Room Move Wizard'

    reservation_id = fields.Many2one(
        'hospitality.reservation',
        string='Reservation',
        required=True,
        help='Reservation undergoing the room move.',
    )

    current_space_id = fields.Many2one(
        'hospitality.space',
        string='Current Room',
        related='reservation_id.space_id',
        readonly=True,
        help='Room currently assigned to the reservation.',
    )

    target_space_id = fields.Many2one(
        'hospitality.space',
        string='Target Room',
        required=True,
        domain="[('id', '!=', current_space_id), "
               "('property_id', '=', property_id), "
               "('status', '=', 'vacant_clean'), "
               "('space_type_id', '=', space_type_id)]",
        help='New vacant & clean room to move the guest into.',
    )

    property_id = fields.Many2one(
        'hospitality.property',
        string='Property',
        compute='_compute_property_id',
        store=False,
        help='Property where the room move is performed.',
    )
    space_type_id = fields.Many2one(
        'hospitality.space.type',
        string='Room Type',
        compute='_compute_property_id',
        store=False,
        help='Room category of the current room.',
    )

    @api.depends('reservation_id', 'current_space_id')
    def _compute_property_id(self):
        """Compute the property and space type from the reservation."""
        for rec in self:
            res = rec.reservation_id
            rec.property_id = res.property_id if res else False
            space_type = False
            if rec.current_space_id:
                space_type = rec.current_space_id.space_type_id
            elif res:
                space_type = getattr(res, 'space_type_id', False)
            rec.space_type_id = space_type

    effective_at = fields.Datetime(
        string='Effective At',
        default=fields.Datetime.now,
        required=True,
        help='Date and time when the room move takes effect.',
    )
    reason = fields.Text(
        string='Reason',
        required=True,
        help='Reason for moving the guest to another room.',
    )
    move_charges_to_new = fields.Boolean(
        string='Move In-Flight Charges to New Room',
        default=True,
        help='Relabel any in-flight charges with the new room context.',
    )

    def _current_user_is_supervisor(self):
        """Return whether the current user belongs to the front desk supervisor group."""
        return self.env.user.has_group(
            'hospitality_front_desk.group_front_desk_supervisor'
        )

    def action_move(self):
        """Move the guest to a different room.

            Validates the target room, applies supervisor override rules,
            updates reservation and housekeeping records, optionally
            relabels in-flight charges, and logs the move in the reservation
            chatter.
            """
        self.ensure_one()

        if not self.reservation_id:
            raise UserError('A reservation is required to perform a room move.')

        current_space = self.current_space_id
        target_space = self.target_space_id

        if not target_space:
            raise UserError('Please select a target room for the move.')

        if not current_space:
            raise UserError(
                'The reservation has no current room assigned to move from.'
            )

        if target_space == current_space:
            raise UserError('The target room must be different from the current room.')

        type_mismatch = (
                current_space.space_type_id
                and target_space.space_type_id
                and target_space.space_type_id != current_space.space_type_id
        )
        not_ready = target_space.status != 'vacant_clean'

        if (type_mismatch or not_ready) and not self._current_user_is_supervisor():
            raise UserError(
                'Target room "%s" is not vacant & clean or does not match the '
                'required room type. A supervisor override is required to '
                'move into this room.' % target_space.code
            )

        self.env.cr.execute(
            'SELECT id FROM hospitality_space WHERE id IN %s FOR UPDATE',
            ((current_space.id, target_space.id),),
        )

        current_space = current_space.browse(current_space.id)
        target_space = target_space.browse(target_space.id)

        if target_space.status != 'vacant_clean' and not self._current_user_is_supervisor():
            raise UserError(
                'Target room "%s" is no longer vacant & clean.' % target_space.code
            )

        old_space = current_space

        self.reservation_id.write({'space_id': target_space.id})

        old_space.action_set_vacant_dirty()

        if target_space.status == 'vacant_clean':
            target_space.action_set_occupied_clean()
        else:
            target_space.write({'status': 'occupied_clean'})

        if self.move_charges_to_new:
            self._relabel_charges(old_space, target_space)

        self.reservation_id.message_post(
            body=
            'Room move: %(old)s → %(new)s.Reason: %(reason)s'
            % {
                'old': old_space.code,
                'new': target_space.code,
                'reason': self.reason,
            }
        )

        return {'type': 'ir.actions.act_window_close'}

    def _relabel_charges(self, old_space, new_space):
        """Best-effort relabel of any in-flight folio charges tied to the
        old space, pointing them at the new space instead.

        Defensive against folio/folio-line schema differences — only acts
        on fields that actually exist on the model.
        """
        Folio = self.env.get('hospitality.folio')
        if Folio is None or 'reservation_id' not in Folio._fields:
            return
        folio = Folio.search(
            [('reservation_id', '=', self.reservation_id.id)], limit=1
        )
        if not folio:
            return

        FolioLine = self.env.get('hospitality.folio.line')
        if FolioLine is None:
            return

        space_field = None
        for fname in ('space_id', 'hospitality_space_id'):
            if fname in FolioLine._fields:
                space_field = fname
                break
        if not space_field:
            return

        lines = self.env['hospitality.folio.line'].search([
            ('folio_id', '=', folio.id),
            (space_field, '=', old_space.id),
        ])
        if lines:
            lines.write({space_field: new_space.id})
