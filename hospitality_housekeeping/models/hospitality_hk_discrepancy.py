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
from odoo.tools.translate import _

from .hospitality_housekeeping_task import (
    RESERVATION_MODEL, RESERVATION_CHECKED_IN_STATE)

HK_STATUS_TO_PMS_CATEGORY = {
    'vacant_clean': 'vacant',
    'vacant_dirty': 'vacant',
    'occupied_clean': 'occupied',
    'occupied_dirty': 'occupied',
    'inspected': 'vacant',
    'pickup': 'vacant',
}


class HospitalityHkDiscrepancy(models.TransientModel):
    """HK-05: a snapshot list of spaces where the housekeeping status
    and PMS occupancy disagree. Rows are (re)computed fresh every
    time action_hk_discrepancy_report() runs -- this is a
    TransientModel, so there's no persistence or write access
    outside that action."""
    _name = 'hospitality.hk.discrepancy'
    _description = 'HK Discrepancy'
    _order = 'space_id'

    space_id = fields.Many2one(
        'hospitality.space', string='Room', required=True, readonly=True,
        help="The hospitality room where a discrepancy exists between "
             "housekeeping status and PMS occupancy.",
    )
    pms_state = fields.Selection([
        ('occupied', 'Occupied'),
        ('vacant', 'Vacant'),
    ], string='PMS State', required=True, readonly=True,
        help="The occupancy state as reported by the PMS system based "
             "on active check-in reservations for this space.",
    )
    hk_state = fields.Char(string='Housekeeping State', readonly=True,
                           help="The current housekeeping status of the room (e.g., vacant_clean, "
                                "occupied_dirty) as reported by the housekeeping team.",
                           )
    note = fields.Char(string='Note', readonly=True,
                       help="A descriptive explanation of the discrepancy, detailing what "
                            "the PMS says versus what the housekeeping status indicates.",
                       )

    @api.model
    def action_hk_discrepancy_report(self):
        """Recompute discrepancies for the current property and open
        a list view scoped to just those rows."""
        Task = self.env['hospitality.housekeeping.task']
        property_id = Task._get_current_property_id()
        records = self._compute_discrepancies(property_id)
        return {
            'name': _('HK Discrepancy'),
            'type': 'ir.actions.act_window',
            'res_model': 'hospitality.hk.discrepancy',
            'view_mode': 'list',
            'domain': [('id', 'in', records.ids)],
            'target': 'current',
        }

    @api.model
    def _compute_discrepancies(self, property_id):
        """Build fresh discrepancy rows for one property: spaces
        where hospitality.space.status disagrees with whether the
        space currently has a checked-in reservation.

        "PMS says occupied" means the space has a reservation in
        state RESERVATION_CHECKED_IN_STATE (defined in
        hospitality_housekeeping_task.py). Confirmed against the
        real hospitality_reservation schema: state value 'checked_in'
        and the property_id/space_id fields match as assumed.

        NOTE: the reservation search always runs, even when
        property_id is falsy (e.g. a user with no assigned
        property) -- it just widens to every space in that case via
        the space_id domain. Previously this search was skipped
        entirely when property_id was falsy, which meant
        occupied_space_ids stayed empty and every occupied-marked
        space would misreport as a discrepancy while real vacant/
        checked-in mismatches were missed.
        """
        Space = self.env['hospitality.space']
        domain = [('property_id', '=', property_id)] if property_id else []
        spaces = Space.search(domain)
        if not spaces:
            return self.browse()

        reservation_domain = [
            ('state', '=', RESERVATION_CHECKED_IN_STATE),
            ('space_id', 'in', spaces.ids),
        ]
        if property_id:
            reservation_domain.append(('property_id', '=', property_id))
        occupied_reservations = self.env[RESERVATION_MODEL].search(
            reservation_domain)
        occupied_space_ids = set(
            occupied_reservations.mapped('space_id').ids)

        status_labels = dict(Space._fields['status'].selection)
        to_create = []
        for space in spaces:
            pms_category = (
                'occupied' if space.id in occupied_space_ids else 'vacant')
            hk_category = HK_STATUS_TO_PMS_CATEGORY.get(space.status)
            if hk_category is None or hk_category == pms_category:
                continue  # out of scope (ooo/oos), or no mismatch
            hk_label = status_labels.get(space.status, space.status)
            pms_label = _('Occupied') if pms_category == 'occupied' \
                else _('Vacant')
            to_create.append({
                'space_id': space.id,
                'pms_state': pms_category,
                'hk_state': hk_label,
                'note': _(
                    'PMS says %(pms)s but housekeeping status is '
                    '%(hk)s.') % {'pms': pms_label, 'hk': hk_label},
            })
        return self.create(to_create) if to_create else self.browse()