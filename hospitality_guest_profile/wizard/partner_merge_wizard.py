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
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC License
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
"""
partner_merge_wizard.py  (GUEST-05)
====================================
Extends base.partner.merge.automatic.wizard:
1. Strips invalid Selection values from the merge write payload so the core
   _update_values call never raises ValueError (e.g. stale 'vip_level' keys).
2. Broadcasts a bus message on channel 'hospitality.guest.merged'
   after a guest merge, carrying {kept_id, merged_ids}.
"""

import json
import logging
from odoo import models
from odoo.exceptions import ValidationError
from odoo.orm.fields_selection import Selection

_logger = logging.getLogger(__name__)


class PartnerMergeAutomaticWizard(models.TransientModel):
    """Extend the core merge wizard to broadcast a bus event for guest merges."""

    _inherit = 'base.partner.merge.automatic.wizard'

    def _sanitize_merge_values(self, dst_partner, values):
        """Remove or nullify values that would fail field validation.

        The core _update_values builds a dict from the source partners and
        writes it onto dst_partner.  If any Selection field carries a key that
        no longer exists in the field's selection list the write raises
        ValueError.  We drop those keys so the merge can proceed.
        """
        Partner = self.env['res.partner']
        safe = {}
        for fname, value in values.items():
            field = Partner._fields.get(fname)
            if field is None:
                safe[fname] = value
                continue
            if isinstance(field, Selection) and value is not False and value is not None:
                valid_keys = {k for k, _ in field._description_selection(self.env)}
                if value not in valid_keys:
                    _logger.warning(
                        'Merge: dropping invalid Selection value %r for field '
                        'res.partner.%s (valid: %s)',
                        value, fname, valid_keys,
                    )
                    continue
            safe[fname] = value
        return safe

    def _update_values(self, src_partners, dst_partner):
        """
        Wrap core _update_values to sanitise the write payload first.
        Monkey-patch dst_partner.write for the duration of this call so that
        any invalid Selection values are silently dropped rather than raising.
        """
        original_write = dst_partner.__class__.write
        def safe_write(self_partner, vals):
            sanitized = self.env[
                'base.partner.merge.automatic.wizard'
            ]._sanitize_merge_values(self_partner, vals)
            return original_write(self_partner, sanitized)

        dst_partner.__class__.write = safe_write
        try:
            return super()._update_values(src_partners, dst_partner)
        finally:
            dst_partner.__class__.write = original_write

    def _merge(self, partner_ids, dst_partner=None, extra_checks=True):
        """
        Override _merge to emit a bus notification when guests are merged.
        Collect guest IDs *before* the merge while all records still exist
        Reassign history lines from source partners to dst before the core
        merge runs (core only handles models it knows about; One2many on
        partner_id for our custom model is not auto-reassigned).
        """
        partners = self.env['res.partner'].browse(partner_ids)
        guest_partners = partners.filtered('is_guest')
        if dst_partner:
            src_partners = partners.filtered(
                lambda p: p.id != dst_partner.id
            )
            history_lines = self.env[
                'hospitality.guest.history.line'
            ].search([
                ('partner_id', 'in', src_partners.ids)
            ])
            for line in history_lines:
                overlap = self.env[
                    'hospitality.guest.history.line'
                ].search([
                    ('partner_id', '=', dst_partner.id),
                    ('check_in', '<', line.check_out),
                    ('check_out', '>', line.check_in),
                ], limit=1)
                if overlap:
                    raise ValidationError(
                        "Cannot merge guests because their stay history overlaps."
                    )
            history_lines.write({
                'partner_id': dst_partner.id
            })
        result = super()._merge(
            partner_ids,
            dst_partner=dst_partner,
            extra_checks=extra_checks,
        )
        if guest_partners and dst_partner:
            kept_id = dst_partner.id
            merged_ids = [p.id for p in guest_partners if p.id != kept_id]
            if merged_ids:
                try:
                    self.env['bus.bus']._sendone(
                        'hospitality.guest.merged',
                        'notification',
                        json.dumps({'kept_id': kept_id, 'merged_ids': merged_ids}),
                    )
                except Exception:
                    _logger.warning(
                        'Could not broadcast hospitality.guest.merged event '
                        'after merging guest IDs %s into %s',
                        merged_ids,
                        kept_id,
                        exc_info=True,
                    )
        return result
