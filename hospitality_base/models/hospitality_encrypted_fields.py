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
import base64
import logging
from odoo import fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
_UNREADABLE = '***UNREADABLE***'


def _get_fernet(env):
    """Fetch the Fernet instance using the configured encryption key.

    Key lookup order:
      1. ir.config_parameter  hospitality.encryption_key
      2. odoo.conf            hospitality_encryption_key

    :raises UserError: if no key is configured.
    :returns Fernet: ready-to-use Fernet instance.
    """
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise UserError(
            "The 'cryptography' Python package is required for encrypted "
            "fields. Install it with: pip install cryptography"
        )
    key = env['ir.config_parameter'].sudo().get_param(
        'hospitality.encryption_key'
    )
    if not key:
        try:
            from odoo.tools import config as odoo_config
            key = odoo_config.get('hospitality_encryption_key', '')
        except Exception:
            pass
    if not key:
        raise UserError(
            "Hospitality encryption key is not configured.\n\n"
            "Go to Settings → Hospitality → Encryption Key and generate "
            "a key, or set 'hospitality_encryption_key' in odoo.conf."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise UserError(
            "The configured hospitality encryption key is invalid: %s" % str(e)
        )

class EncryptedChar(fields.Char):
    """A Char field that transparently encrypts values at rest.

    Stores Fernet-encrypted, base64-encoded ciphertext in the database column.
    Returns plaintext on read; returns ``***UNREADABLE***`` if decryption fails.
    """

    type = 'char'

    def convert_to_column(self, value, record, values=None, validate=True):
        """Encrypt plaintext before writing to the database."""
        if not value:
            return super().convert_to_column(
                value, record, values=values, validate=validate
            )
        try:
            fernet = _get_fernet(record.env)
            ciphertext = fernet.encrypt(value.encode('utf-8'))
            return base64.urlsafe_b64encode(ciphertext).decode('ascii')
        except UserError:
            raise
        except Exception as e:
            _logger.error("EncryptedChar.convert_to_column failed: %s", e)
            raise UserError(
                "Failed to encrypt field value. Check encryption key config."
            )

    def convert_to_record(self, value, record):
        """Decrypt ciphertext when reading from the database."""
        if not value:
            return value
        try:
            fernet = _get_fernet(record.env)
            raw = base64.urlsafe_b64decode(value.encode('ascii'))
            return fernet.decrypt(raw).decode('utf-8')
        except UserError:
            raise
        except Exception as e:
            _logger.warning(
                "EncryptedChar.convert_to_record decryption failed "
                "(field may have been written with a different key): %s", e
            )
            return _UNREADABLE

class EncryptedBinary(fields.Binary):
    """A Binary field that encrypts payload bytes before storing.
    Works with Odoo's attachment-backed binary storage.
    Encrypts bytes on write; decrypts on read.
    Returns b'' if decryption fails (logged as a warning).
    """

    def convert_to_column(self, value, record, values=None, validate=True):
        """Encrypt binary payload before storing."""
        if not value:
            return super().convert_to_column(
                value, record, values=values, validate=validate
            )
        try:
            fernet = _get_fernet(record.env)
            if isinstance(value, str):
                raw = base64.b64decode(value)
            else:
                raw = value
            encrypted = fernet.encrypt(raw)
            return base64.b64encode(encrypted).decode('ascii')
        except UserError:
            raise
        except Exception as e:
            _logger.error("EncryptedBinary.convert_to_column failed: %s", e)
            raise UserError(
                "Failed to encrypt binary value. Check encryption key config."
            )

    def convert_to_record(self, value, record):
        """Decrypt binary payload on read."""
        if not value:
            return value
        try:
            fernet = _get_fernet(record.env)
            if isinstance(value, str):
                raw = base64.b64decode(value.encode('ascii'))
            else:
                raw = value
            decrypted = fernet.decrypt(raw)
            return base64.b64encode(decrypted).decode('ascii')
        except UserError:
            raise
        except Exception as e:
            _logger.warning(
                "EncryptedBinary.convert_to_record decryption failed: %s", e
            )
            return b''
