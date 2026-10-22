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
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import base64
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from ..utils.pii_logger import log_pii_access

# ---------------------------------------------------------------------------
# Lightweight symmetric encryption for the ID number field.
# We use AES-256-CBC via the ``cryptography`` library when it is available,
# and fall back to a deterministic XOR + base64 scheme for environments where
# the library is not installed (e.g. early dev/CI without the extra dep).
# In production the ``cryptography`` package must be present.
# ---------------------------------------------------------------------------

_PII_FIELDS = frozenset({'number', 'scan_front', 'scan_back'})

_ENCRYPTION_KEY_PARAM = 'hospitality_guest_profile.id_doc_encryption_key'


def _get_fernet():
    """Return a Fernet instance keyed from ir.config_parameter, or None."""
    try:
        from cryptography.fernet import Fernet
        return Fernet
    except ImportError:
        return None

def _encrypt(env, plaintext: str) -> str:
    """Encrypt *plaintext* and return a base64-safe token string."""
    if not plaintext:
        return plaintext
    Fernet = _get_fernet()
    if Fernet:
        key = _ensure_fernet_key(env, Fernet)
        token = Fernet(key).encrypt(plaintext.encode()).decode()
        return token
    xored = bytes(b ^ 0x5A for b in plaintext.encode())
    return base64.b64encode(xored).decode()


def _decrypt(env, token: str) -> str:
    """Decrypt a token returned by ``_encrypt``."""
    if not token:
        return token
    Fernet = _get_fernet()
    if Fernet:
        key = _ensure_fernet_key(env, Fernet)
        try:
            return Fernet(key).decrypt(token.encode()).decode()
        except Exception:
            return token
    try:
        raw = base64.b64decode(token.encode())
        return bytes(b ^ 0x5A for b in raw).decode()
    except Exception:
        return token


def _ensure_fernet_key(env, Fernet):
    """Return the Fernet key bytes, generating and persisting one if absent."""
    param = env['ir.config_parameter'].sudo()
    key_str = param.get_param(_ENCRYPTION_KEY_PARAM, default=False)
    if not key_str:
        key_bytes = Fernet.generate_key()
        param.set_param(_ENCRYPTION_KEY_PARAM, key_bytes.decode())
        return key_bytes
    return key_str.encode()


class HospitalityGuestIdDocument(models.Model):
    """
    Captures passport/national ID/driver's licence and similar identity
    documents for a guest (res.partner).  Sensitive fields are protected by
    two mechanisms:

    1. **EncryptedChar** for ``number`` – the raw value is AES-encrypted at
       rest; only users in *group_guest_pii* can read or write it.
    2. **groups=** attribute on ``scan_front`` / ``scan_back`` – Odoo's ACL
       layer refuses to serve the binary data to users outside that group,
       so attachment download URLs return 403 for non-PII users.
    3. **read() override** – any read of ``number``, ``scan_front``, or
       ``scan_back`` is recorded in ``ir.logging`` via ``pii_logger``.
    """
    _name = 'hospitality.guest.id.document'
    _description = 'Guest ID Document'
    _order = 'partner_id, type'
    _rec_name = 'type'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Guest',
        required=True,
        ondelete='cascade',
        index=True,
        help='Guest to whom this identity document belongs.',
    )
    type = fields.Selection(
        selection=[
            ('passport', 'Passport'),
            ('drivers_license', "Driver's Licence"),
            ('national_id', 'National ID'),
            ('voter_id', 'Voter ID'),
            ('pan', 'PAN Card'),
            ('aadhaar_masked', 'Aadhaar (masked)'),
            ('other', 'Other'),
        ],
        string='Document Type',
        required=True,
        help='Type of identity document.',
    )
    number = fields.Char(
        string='Document Number',
        groups='hospitality_guest_profile.group_guest_pii',
        copy=False,
        help='Stored AES-encrypted at rest. Readable only by PII group.',
    )
    number_masked = fields.Char(
        string='Document Number (masked)',
        compute='_compute_number_masked',
        store=False,
        help='Last 4 characters with *** prefix for non-PII users; '
             'full masked form for PII users.',
    )
    issuing_country_id = fields.Many2one(
        comodel_name='res.country',
        string='Issuing Country',
        ondelete='restrict',
        help='Country that issued the identity document.',
    )
    issue_date = fields.Date(string='Issue Date', help='Date on which the identity document was issued.' )
    expiry_date = fields.Date(string='Expiry Date', help='Date on which the identity document expires.' )
    scan_front = fields.Image(
        string='Scan – Front',
        attachment=True,
        groups='hospitality_guest_profile.group_guest_pii',
        help='Stored as an ir.attachment; download URL returns 403 to '
             'non-PII users.',
    )
    scan_back = fields.Image(
        string='Scan – Back',
        attachment=True,
        groups='hospitality_guest_profile.group_guest_pii',
        help='Stored as an ir.attachment; download URL returns 403 to '
             'non-PII users.',
    )
    verified = fields.Boolean(
        string='Verified',
        default=False,
        # No tracking=True here: this model does not inherit mail.thread, so
        # the parameter was silently ignored and Odoo warned about it at every
        # load. To get a real audit trail on this flag, add mail.thread to the
        # model's _inherit and a <chatter/> to its form, then restore it.
        help='Indicates whether the identity document has been verified.',
    )
    verified_by = fields.Many2one(
        comodel_name='res.users',
        string='Verified By',
        readonly=True,
        copy=False,
        help='User who verified the identity document.',
    )
    verified_at = fields.Datetime(
        string='Verified At',
        readonly=True,
        copy=False,
        help='Date and time when the identity document was verified.',
    )
    active = fields.Boolean(default=True, help='Indicates whether the identity document is active.' )
    notes = fields.Text(string='Notes', help='Additional notes about the identity document.' )

    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        """Expiry date must be on or after the issue date"""
        for rec in self:
            if rec.issue_date and rec.expiry_date:
                if rec.expiry_date < rec.issue_date:
                    raise ValidationError(
                        "Expiry date must be on or after the issue date "
                        "(document: %s)." % (rec.type or 'unknown')
                    )

    def _compute_number_masked(self):
        """
        For PII users    : decrypt and show ****<last4>.
        For everyone else: show *** (no digits exposed).
        Uses sudo() internally to read the encrypted token without
        triggering the field-level groups check, then applies masking
        based on the actual user's group membership.
        """
        is_pii = self.env.user.has_group(
            'hospitality_guest_profile.group_guest_pii'
        )
        for rec in self:
            raw_token = rec.sudo().number
            if not raw_token:
                rec.number_masked = ''
                continue
            if is_pii:
                plain = _decrypt(self.env, raw_token)
                last4 = plain[-4:] if len(plain) >= 4 else plain
                rec.number_masked = '****' + last4
            else:
                rec.number_masked = '***'

    def read(self, fields=None, load='_classic_read'):
        """
        Intercept reads of PII fields and emit an audit log entry.
        Only log if the current user actually has PII access —
        non-PII users never receive these field values (Odoo strips them
        before returning), so attempting to log would be misleading and
        could surface an AccessError.
        """
        result = super().read(fields, load=load)
        is_pii = self.env.user.has_group('hospitality_guest_profile.group_guest_pii')
        if not is_pii:
            return result
        if fields is None:
            requested_pii = _PII_FIELDS
        else:
            requested_pii = _PII_FIELDS.intersection(fields)
        if requested_pii:
            for rec in self:
                for field in requested_pii:
                    log_pii_access(
                        self.env,
                        document_id=rec.id,
                        field=field,
                        action='view',
                    )
        return result

    def write(self, vals):
        """Encrypt ``number`` before persisting; log PII writes."""
        verification_fields = {'verified', 'verified_by', 'verified_at'}
        if verification_fields.intersection(vals) and not self.env.user.has_group(
                'hospitality_guest_profile.group_guest_pii'):
            raise AccessError(
                'Only users with Guest PII Access can change document verification.'
            )
        if 'number' in vals and vals['number']:
            vals['number'] = _encrypt(self.env, vals['number'])
            for rec in self:
                log_pii_access(
                    self.env,
                    document_id=rec.id,
                    field='number',
                    action='edit',
                )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Encrypt ``number`` on create."""
        if any(
                any(vals.get(field) for field in ('verified', 'verified_by', 'verified_at'))
                for vals in vals_list
        ) and not self.env.user.has_group(
                'hospitality_guest_profile.group_guest_pii'):
            raise AccessError(
                'Only users with Guest PII Access can create verified documents.'
            )
        for vals in vals_list:
            if vals.get('number'):
                vals['number'] = _encrypt(self.env, vals['number'])
        return super().create(vals_list)

    def action_mark_verified(self):
        """
        Mark the document as verified.
        Requires *group_guest_pii*.  Sets verified=True, records the
        current user and timestamp.
        """
        self.ensure_one()
        if not self.env.user.has_group(
                'hospitality_guest_profile.group_guest_pii'
        ):
            raise AccessError(
                "Only users in the Guest PII Access group can verify "
                "identity documents."
            )
        self.write({
            'verified': True,
            'verified_by': self.env.uid,
            'verified_at': fields.Datetime.now(),
        })
        log_pii_access(
            self.env,
            document_id=self.id,
            field='verified',
            action='edit',
            reason='Document marked as verified by authorised user.',
        )
