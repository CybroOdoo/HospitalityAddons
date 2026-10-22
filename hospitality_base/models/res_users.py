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
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# The backend theme's app drawer. res.users.action_id decides where a
# user lands after signing in, and the drawer is this suite's landing
# page. Moved here when hospitality_theme was merged into this module.
HOME_XMLID = 'hospitality_base.action_home'

class ResUsers(models.Model):
    """Extension of standard users model for property management."""
    _inherit = 'res.users'

    property_ids = fields.Many2many(
        comodel_name='hospitality.property',
        relation='hospitality_property_users_rel',
        column1='user_id',
        column2='property_id',
        string='Allowed Properties',
        help='Properties this user is permitted to operate in.',
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Current Property',
        compute='_compute_current_property',
        store=True,
        readonly=False,
        copy=False,
        help='The property the user is currently working in.',
    )

    @api.depends('property_ids')
    def _compute_current_property(self):
        """Keep property_id in sync with the allowed list.
        - If the stored value is still in property_ids → keep it.
        - Otherwise reset to the first allowed property (or False).
        """
        for user in self:
            allowed = user.property_ids
            if user.property_id and user.property_id in allowed:
                continue
            user.property_id = allowed[:1] if allowed else False

    @api.constrains('property_id', 'property_ids')
    def _check_property_in_allowed(self):
        """property_id must be one of property_ids (or empty)."""
        for user in self:
            if user.property_id and user.property_id not in user.property_ids:
                raise ValidationError(
                    "Current property '%s' is not in the list of allowed "
                    "properties for user '%s'. Please add it first."
                    % (user.property_id.name, user.name)
                )

    def _get_property_context(self):
        """Return a dict suitable for injecting into action contexts."""
        self.ensure_one()
        return {'default_property_id': self.property_id.id}

    # ------------------------------------------------------------------
    #  Landing page (backend theme app drawer)
    # ------------------------------------------------------------------
    #  Deliberately conservative: this only ever FILLS an empty action_id.
    #  A user who has already chosen a landing page keeps it, and nothing
    #  is overwritten on upgrade. Pass force=True from a shell to reset
    #  everyone.

    @api.model
    def _ht_home_action(self):
        return self.env.ref(HOME_XMLID, raise_if_not_found=False)

    def _ht_set_home_action(self, force=False):
        """Point users at the drawer, without clobbering a choice."""
        action = self._ht_home_action()
        if not action:
            return
        targets = self if force else self.filtered(lambda u: not u.action_id)
        if targets:
            targets.sudo().write({'action_id': action.id})
            _logger.info(
                'Hospitality drawer set as home action for %d user(s).',
                len(targets),
            )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._ht_set_home_action()
        return users


def post_init_hook(env):
    """Assign the drawer to users already present at install."""
    env['res.users'].search([('active', 'in', (True, False))]) \
        ._ht_set_home_action()
