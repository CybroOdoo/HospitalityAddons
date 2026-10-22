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


class HospitalityLostFound(models.Model):
    """A lost & found item, tracked from the moment it's logged
    through storage, return to its owner, donation, or disposal.
    State changes are tracked via mail.thread so the chatter carries
    a timestamped history of every transition (who moved it, when)."""
    _name = 'hospitality.lost.found'
    _description = 'Lost & Found Item'
    _inherit = ['mail.thread', 'hospitality.mixin.property']
    _order = 'found_at desc'

    name = fields.Char(
        string='Name', compute='_compute_name', store=True,
        help='Readable label, e.g. "Room 102 - Found 07/06/2026".')
    property_id = fields.Many2one(
        'hospitality.property', string='Property', required=True,
        index=True,help="The hospitality property where the item was found and is being stored.",)
    found_at = fields.Datetime(
        string='Found At', default=fields.Datetime.now, required=True,
        help="Timestamp when the item was discovered. Defaults to the "
             "current time when the record is created.",
    )
    found_in_space_id = fields.Many2one(
        'hospitality.space', string='Found In Room',
        help="The specific room, suite, or area where the item was found. "
             "Helps in returning the item to the correct guest.",
    )
    description = fields.Text(required=True,string='Description',
                              help="Detailed description of the item, including its appearance, "
                                   "condition, and any distinguishing features. Used for "
                                   "identification when guests inquire about lost items.",
                              )
    photo = fields.Binary(string='Photo', attachment=True)
    finder_id = fields.Many2one(
        'res.users', string='Finder', default=lambda self: self.env.uid)
    owner_partner_id = fields.Many2one(
        'res.partner', string='Owner',
        help='Set once the item has been claimed by its owner.')
    state = fields.Selection([
        ('logged', 'Logged'),
        ('stored', 'Stored'),
        ('returned', 'Returned'),
        ('donated', 'Donated'),
        ('disposed', 'Disposed'),
    ], required=True, default='logged', tracking=True)
    storage_location = fields.Char()
    notes = fields.Text()

    @api.depends('found_in_space_id', 'property_id', 'found_at')
    def _compute_name(self):
        """Compute a descriptive name using the location where the item
            was found and the discovery timestamp."""
        for item in self:
            location = (
                item.found_in_space_id.display_name
                or item.property_id.display_name
                or _('New Item'))
            date_str = (
                fields.Datetime.to_string(item.found_at)
                if item.found_at else _('No Date'))
            item.name = f'{location} - Found {date_str}'

    def write(self, vals):
        """Log every state transition on the chatter explicitly.

        `state` is marked tracking=True so mail.thread's automatic
        field tracking would normally handle this, but that behavior
        depends on hospitality.mixin.property's write()/create()
        chain (defined in hospitality_property, not this module), and
        this module can't verify or control what that mixin does to
        the write() MRO. Logging explicitly here keeps the audit
        trail self-contained and independent of that dependency.
        """
        state_labels = dict(self._fields['state'].selection)
        old_states = {rec.id: rec.state for rec in self} \
            if 'state' in vals else {}
        res = super().write(vals)
        if 'state' in vals:
            for rec in self:
                old_state = old_states.get(rec.id)
                new_state = rec.state
                if old_state and old_state != new_state:
                    rec.message_post(body=_(
                        'Status changed from %(old)s to %(new)s.') % {
                            'old': state_labels.get(old_state, old_state),
                            'new': state_labels.get(new_state, new_state),
                        })
        return res

    def _ensure_state(self, expected_states):
        """Validate that all selected items are in one of the expected
            states before allowing the requested action."""
        wrong = self.filtered(lambda r: r.state not in expected_states)
        if wrong:
            raise UserError(_(
                'This action is not allowed from the current state of '
                'item(s): %s.') % ', '.join(wrong.mapped('display_name')))

    def action_store(self, storage_location=None):
        """logged -> stored. Optionally records where it's stored."""
        self._ensure_state(['logged'])
        vals = {'state': 'stored'}
        if storage_location:
            vals['storage_location'] = storage_location
        return self.write(vals)

    def action_return(self, owner_partner_id=None):
        """stored -> returned. Optionally records who claimed it."""
        self._ensure_state(['stored'])
        vals = {'state': 'returned'}
        if owner_partner_id:
            vals['owner_partner_id'] = owner_partner_id
        return self.write(vals)

    def action_donate(self):
        """stored -> donated (never claimed by an owner)."""
        self._ensure_state(['stored'])
        return self.write({'state': 'donated'})

    def action_dispose(self):
        """logged or stored -> disposed."""
        self._ensure_state(['logged', 'stored'])
        return self.write({'state': 'disposed'})