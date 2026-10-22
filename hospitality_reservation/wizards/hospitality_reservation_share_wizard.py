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


class HospitalityReservationShareWizard(models.TransientModel):
    """Wizard for linking a sharer to an existing reservation.

    Two modes:
    • create_new   — copies the source reservation with a different guest
                     and links both ends of share_with_ids.
    • attach_existing — validates an already-existing reservation and links
                     both ends of share_with_ids.
    """
    _name = 'hospitality.reservation.share.wizard'
    _description = 'Add Sharer Wizard'

    source_reservation_id = fields.Many2one(
        'hospitality.reservation',
        string='Source Reservation',
        required=True,
        readonly=True,
        help='Main reservation that will share its room with another guest.',
    )
    mode = fields.Selection(
        selection=[
            ('create_new', 'Create new sharer reservation'),
            ('attach_existing', 'Attach an existing reservation'),
        ],
        string='Mode',
        required=True,
        default='create_new',
        help='Choose to create a new sharer reservation or link an existing one.',
    )
    target_reservation_id = fields.Many2one(
        'hospitality.reservation',
        string='Existing Reservation',
        domain="[('id', '!=', source_reservation_id),"
               " ('property_id', '=', source_property_id)]",
        help='Existing reservation to link as sharer. Must be in same property.',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Sharer Guest',
        help='The second guest who will share the room.',
    )
    source_property_id = fields.Many2one(
        related='source_reservation_id.property_id',
        string='Property',
        readonly=True,
        store=False,
        help='Property of the source reservation. Read-only for context.',
    )

    def _validate_sharer_dates(self, source, target):
        """Raise UserError if source and target don't overlap in dates."""
        if source.arrival and source.departure \
                and target.arrival and target.departure:
            if target.departure <= source.arrival \
                    or target.arrival >= source.departure:
                raise UserError(
                    'Reservation %(target)s does not overlap in dates '
                      'with %(source)s.',
                      target=target.name, source=source.name
                )

    def _validate_sharer_space(self, source, target):
        """Raise UserError if both have a space and they differ."""
        if source.space_id and target.space_id \
                and source.space_id != target.space_id:
            raise UserError(
                'Sharer reservation %(target)s must use the same '
                  'room as %(source)s (%(room)s).',
                  target=target.name,
                  source=source.name,
                  space=source.space_id.name
            )

    def action_apply(self):
        """Apply the share operation based on the chosen mode."""
        self.ensure_one()
        source = self.source_reservation_id
        if self.mode == 'create_new':
            return self._apply_create_new(source)
        else:
            return self._apply_attach_existing(source)

    def _apply_create_new(self, source):
        """Copy source, assign the new partner, link both share_with_ids ends."""
        if not self.partner_id:
            raise UserError(
                'Please select the sharer guest before applying.'
            )
        sharer = source.copy(default={
            'partner_id': self.partner_id.id,
            'share_with_ids': [],  # avoid recursive copy
            'state': 'draft',
        })
        source.write({'share_with_ids': [(4, sharer.id)]})
        sharer.write({'share_with_ids': [(4, source.id)]})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.reservation',
            'res_id': sharer.id,
            'views': [(False, 'form')],
            'target': 'current',
        }

    def _apply_attach_existing(self, source):
        """Validate and link an already-existing sharer reservation."""
        if not self.target_reservation_id:
            raise UserError(
                'Please select the existing reservation to attach.'
            )
        target = self.target_reservation_id

        if target == source:
            raise UserError('A reservation cannot be its own sharer.')

        if target in source.share_with_ids:
            raise UserError(
                '%(target)s is already linked as a sharer of %(source)s.',
                  target=target.name, source=source.name
            )

        self._validate_sharer_dates(source, target)
        self._validate_sharer_space(source, target)
        source.write({'share_with_ids': [(4, target.id)]})
        target.write({'share_with_ids': [(4, source.id)]})
        return {'type': 'ir.actions.act_window_close'}
