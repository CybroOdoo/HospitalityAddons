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
"""
pii_logger.py
=============
Helper for auditing access to personally identifiable information (PII)
in the Hospitality Guest Profile module.

Every time a privileged field (e.g. government ID number, ID scan) is read
or written, call ``log_pii_access`` to write a structured entry to
``ir.logging``.  The entries can then be reviewed by security auditors via
Settings ▸ Technical ▸ Logging.

Log characteristics
-------------------
* type    : ``server``
* channel : ``hospitality.pii``
* level   : ``INFO``

Log message format
------------------
    PII {action} | user={login} (id={uid}) | document={document_id}
    | field={field} | reason={reason}
"""

import logging

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CHANNEL = 'hospitality.pii'
_LEVEL = 'INFO'
_LOG_TYPE = 'server'

_VALID_ACTIONS = frozenset({'view', 'edit', 'export', 'print', 'delete'})


def log_pii_access(env, document_id, field, action='view', reason=None):
    """Write a PII-access audit entry to ``ir.logging``.

    Parameters
    ----------
    env : odoo.api.Environment
        Active Odoo environment (used to resolve the current user and to
        create the ``ir.logging`` record).
    document_id : int | str
        Database ID (or any stable string reference) of the record whose
        PII field is being accessed.  Typically a ``hospitality.guest`` id.
    field : str
        Technical field name that was accessed, e.g. ``'gov_id_number'``
        or ``'gov_id_scan'``.
    action : str, optional
        One of ``'view'``, ``'edit'``, ``'export'``, ``'print'``,
        ``'delete'``.  Defaults to ``'view'``.
    reason : str | None, optional
        Free-text business justification supplied by the user or the calling
        code.  Stored as-is; ``None`` is recorded as ``'not provided'``.

    Returns
    -------
    ir.logging
        The newly created log record (useful for testing).

    Raises
    ------
    ValueError
        If *action* is not one of the recognised values.

    Examples
    --------
    >>> log_pii_access(env, guest.id, 'gov_id_number', action='view',
    ...                reason='Check-in verification')
    """
    # ------------------------------------------------------------------
    # Validate action
    # ------------------------------------------------------------------
    if action not in _VALID_ACTIONS:
        raise ValueError(
            "log_pii_access: invalid action %r. "
            "Must be one of: %s" % (action, ', '.join(sorted(_VALID_ACTIONS)))
        )

    # ------------------------------------------------------------------
    # Resolve current user details
    # ------------------------------------------------------------------
    user = env.user
    uid = env.uid
    login = user.login if user else 'unknown'
    reason_text = reason if reason is not None else 'not provided'

    # ------------------------------------------------------------------
    # Build log message
    # ------------------------------------------------------------------
    message = (
        "PII %(action)s | "
        "user=%(login)s (id=%(uid)s) | "
        "document=%(document_id)s | "
        "field=%(field)s | "
        "reason=%(reason)s"
    ) % {
        'action': action.upper(),
        'login': login,
        'uid': uid,
        'document_id': document_id,
        'field': field,
        'reason': reason_text,
    }

    # ------------------------------------------------------------------
    # Also emit to the Python logger so the entry appears in the Odoo
    # server log file / stdout, independent of ir.logging availability.
    # ------------------------------------------------------------------
    _logger.info(message)

    # ------------------------------------------------------------------
    # Persist to ir.logging
    # Use sudo() so the write succeeds regardless of the caller's ACL,
    # but we still record *their* identity in the message above.
    # ------------------------------------------------------------------
    log_record = env['ir.logging'].sudo().create({
        'name': 'hospitality.guest',
        'type': _LOG_TYPE,
        'level': _LEVEL,
        'dbname': env.cr.dbname,
        'message': message,
        'path': 'hospitality_guest_profile/utils/pii_logger.py',
        'func': 'log_pii_access',
        'line': 0,
    })

    return log_record