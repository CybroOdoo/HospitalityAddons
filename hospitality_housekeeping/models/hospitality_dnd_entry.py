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
from odoo.exceptions import UserError
from odoo.tools.translate import _


class HospitalityDndEntry(models.Model):
    """Audit log of Do Not Disturb periods on a space. Kept separate
    from the housekeeping task's own dnd/pending side-path so
    supervisors have a durable record of every DND period on a space
    (who set it, why, who cleared it, and when) independent of any
    single task's lifecycle."""
    _name = 'hospitality.dnd.entry'
    _description = 'Housekeeping DND Entry'
    _order = 'set_at desc'

    name = fields.Char(
        string='Name', compute='_compute_name', store=True,
        help='Readable label, e.g. "Room 102 DND - 07/06/2026".')
    space_id = fields.Many2one(
        'hospitality.space', string='Room', required=True, index=True,
        help="The hospitality room (room, suite, etc.) where the Do Not "
             "Disturb period is being applied.",
    )
    set_at = fields.Datetime(
        string='Set At', default=fields.Datetime.now, required=True,
        help="Timestamp when the DND period was set. Defaults to the "
             "current time when the entry is created.",
    )
    set_by = fields.Many2one(
        'res.users', string='Set By', default=lambda self: self.env.uid,
        help="The user who set the DND period on the room.",
    )
    reason = fields.Char(string='Reason',help="Optional reason for setting the DND period, e.g., guest request, "
             "privacy concern, or maintenance activity.",)
    cleared_at = fields.Datetime(string='Cleared At',help="Timestamp when the DND period was cleared. Populated when "
             "the DND entry is cleared",)
    cleared_by = fields.Many2one('res.users', string='Cleared By',
                                 help="The user who cleared the DND period. Populated when the "
                                      "DND entry is cleared",
                                 )

    @api.depends('space_id', 'set_at')
    def _compute_name(self):
        """Generate a descriptive name for the DND entry.

        Combines the space name and the timestamp when the DND period was
        created.
        """
        for entry in self:
            space_name = entry.space_id.display_name or _('New Room')
            date_str = (
                fields.Datetime.to_string(entry.set_at)
                if entry.set_at else _('No Date'))
            entry.name = f'{space_name} DND - {date_str}'

    def action_clear(self):
        """Mark the DND entry cleared, stamping who cleared it and
        when. Raises if it has already been cleared."""
        for entry in self:
            if entry.cleared_at:
                raise UserError(_(
                    'This DND entry for %s has already been cleared.'
                ) % entry.space_id.display_name)
            entry.write({
                'cleared_at': fields.Datetime.now(),
                'cleared_by': self.env.uid,
            })
        return True