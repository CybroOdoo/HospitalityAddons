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


class HospitalityReservation(models.Model):
    """NA-05: hospitality.folio.reservation_id (hospitality_folio) has never
    had a matching reverse One2many declared on hospitality.reservation —
    neither hospitality_folio's own FOL-05 routing extension (which only
    adds routing_instruction_ids) nor hospitality_reservation itself
    declares one. Several NA-03 steps already anticipated this gap
    defensively (`if 'folio_ids' not in res._fields: continue`), which
    means _step_post_room_charges / _step_post_package_inclusions /
    _step_post_in_house_deposits have been silently no-op'ing on every
    property since NA-03 shipped — the guard never fires false, so
    reservations are never able to look up their folio at all.

    Adding the inverse here (rather than in hospitality_folio, which this
    module doesn't own) is the minimal fix that lets NA-05's integration
    test — and real night audits — actually post room charges. If
    hospitality_folio later adds its own folio_ids, this becomes a
    duplicate declaration and should be removed in favour of that one.
    """
    _inherit = 'hospitality.reservation'

    folio_ids = fields.One2many(
        comodel_name='hospitality.folio',
        inverse_name='reservation_id',
        string='Folios',
        help="The folios associated with this reservation. This reverse "
             "relationship enables night audit steps to locate and post "
             "room charges, package inclusions, and other transactions "
             "to the guest's folio from the reservation context.",
    )