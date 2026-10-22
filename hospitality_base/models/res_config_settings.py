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

class ResConfigSettings(models.TransientModel):
    """Extension of standard odoo setting model for Hospitality Management."""
    _inherit = 'res.config.settings'

    hospitality_encryption_key_hint = fields.Char(
        string='Hospitality Encryption Key',
        compute='_compute_encryption_key_hint',
        help='Shows the last 4 characters of the configured Fernet key. '
             'Use "Generate New Key" to create a fresh one.',
        readonly=True,
    )

    @api.depends()
    def _compute_encryption_key_hint(self):
        """Show only the last 4 chars for security."""
        key = self.env['ir.config_parameter'].sudo().get_param(
            'hospitality.encryption_key', default=''
        )
        for rec in self:
            if key:
                rec.hospitality_encryption_key_hint = (
                    '…' + key[-4:]
                )
            else:
                rec.hospitality_encryption_key_hint = 'Not configured'

    def action_generate_encryption_key(self):
        """Generate a new Fernet encryption key and store it.

        WARNING: Rotating the key will make all previously encrypted data
        unreadable.  Only do this on a fresh installation.
        """
        self.ensure_one()
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            raise models.UserError(
                "The 'cryptography' Python package is not installed."
            )
        new_key = Fernet.generate_key().decode('ascii')
        self.env['ir.config_parameter'].sudo().set_param(
            'hospitality.encryption_key', new_key
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Encryption Key Generated',
                'message': (
                    'A new Fernet key has been stored. '
                    'Refresh the page to see the updated hint.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
