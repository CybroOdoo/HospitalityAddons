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

class HospitalityQueueEntry(models.Model):
    """FD-05 — Queue an arrival when its assigned room is not yet ready.

    Entries are typically created when a check-in is attempted but the
    target space is still vacant_dirty / being serviced. The housekeeping
    board flips an entry to 'ready' once the room becomes vacant_clean,
    notifying the front desk so the guest can be checked in.
    """
    _name = 'hospitality.queue.entry'
    _description = 'Front Desk Arrival Queue Entry'
    _inherit = ['mail.thread']
    _order = 'queued_at'

    reservation_id = fields.Many2one(
        'hospitality.reservation',
        string='Reservation',
        required=True,
        tracking=True,
        help='Reservation queued awaiting room readiness.',
    )
    queued_at = fields.Datetime(
        string='Queued At',
        default=fields.Datetime.now,
        required=True,
        help='Date and time when the arrival was placed in the queue.',
    )
    ready_at = fields.Datetime(
        string='Ready At',
        help='Date and time when the room became ready.',
    )
    called_by = fields.Many2one(
        'res.users',
        string='Called By',
        help='Front desk or housekeeping user who marked the entry ready.',
    )
    state = fields.Selection(
        [
            ('waiting', 'Waiting'),
            ('ready', 'Ready'),
            ('served', 'Served'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='waiting',
        required=True,
        tracking=True,
        help='Current status of the queue entry.',
    )

    def action_mark_ready(self):
        """Flip a waiting entry to 'ready' and notify the front desk.

        Intended to be called by the housekeeping board once the linked
        reservation's space becomes vacant_clean.
        """
        for rec in self:
            if rec.state != 'waiting':
                continue
            rec.write({
                'ready_at': fields.Datetime.now(),
                'called_by': self.env.user.id,
                'state': 'ready',
            })
            rec._notify_front_desk()

    def action_mark_served(self):
        """Mark ready queue entries as served."""
        for rec in self:
            if rec.state == 'ready':
                rec.write({'state': 'served'})

    def action_cancel(self):
        """Cancel waiting or ready queue entries."""
        for rec in self:
            if rec.state in ('waiting', 'ready'):
                rec.write({'state': 'cancelled'})

    def _notify_front_desk(self):
        """Best-effort notification to front desk users that a room is
        ready for an in-house guest waiting in the arrival queue.
        """
        self.ensure_one()
        agent_group = self.env.ref(
            'hospitality_front_desk.group_front_desk_agent',
            raise_if_not_found=False,
        )
        partner_ids = []
        if agent_group:
            agents = self.env['res.users'].search(
                [('group_ids', 'in', agent_group.id)]
            )
            partner_ids = agents.partner_id.ids
        self.message_post(
            body=(
                    'Room is ready for %(guest)s (reservation %(res)s).'
                    % {
                        'guest': self.reservation_id.partner_id.name or '',
                        'res': self.reservation_id.display_name,
                    }
            ),
            partner_ids=partner_ids,
        )