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


class HospitalityFolioWindow(models.Model):
    """Manage billing windows within a hospitality folio.

        A folio can contain multiple billing windows (up to eight), each
        representing a separate payer or billing category. Windows are used
        for charge routing and split-billing scenarios.
        """
    _name = "hospitality.folio.window"
    _description = "Folio Billing Window"
    _order = "folio_id, sequence"
    _rec_name = 'label'

    folio_id = fields.Many2one(
        "hospitality.folio",
        string="Folio",
        required=True,
        ondelete="cascade",
        index=True,
        help="Folio associated with this billing window.",
    )
    sequence = fields.Integer(
        string="Window #",
        required=True,
        default=1,
        help="Window number within the folio (1–8). "
             "Window 1 is the primary billing window.",
    )
    label = fields.Char(
        string="Label",
        help='Descriptive name, e.g. "Room", "F&B", "Incidentals".',
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Payer",
        ondelete="restrict",
        help="Payer for this window. Defaults to the folio's primary payer.",
    )
    routing_rule_ids = fields.One2many(
        "hospitality.routing.instruction",
        "target_window_id",
        string="Routing Rules",
        help="Routing instructions directing charges to this window.",
    )

    @api.constrains("sequence", "folio_id")
    def _check_unique_sequence(self):
        """Ensure each window sequence is unique within a folio."""
        for win in self:
            duplicate = self.search([
                ("folio_id", "=", win.folio_id.id),
                ("sequence", "=", win.sequence),
                ("id", "!=", win.id),
            ], limit=1)
            if duplicate:
                raise UserError(
                        "Window sequence %(seq)s already exists on folio %(folio)s.",
                        seq=win.sequence,
                        folio=win.folio_id.name,
                )

    @api.constrains("sequence")
    def _check_sequence_range(self):
        """Validate that the window sequence is between 1 and 8."""
        for win in self:
            if not (1 <= win.sequence <= 8):
                raise UserError(
                        "Window sequence must be between 1 and 8 "
                        "(window %(seq)s on folio %(folio)s).",
                        seq=win.sequence,
                        folio=win.folio_id.name,
                )

    @api.onchange("folio_id")
    def _onchange_folio_id(self):
        """Default the window payer to the folio's primary payer."""
        if self.folio_id and not self.partner_id:
            self.partner_id = self.folio_id.partner_id

    @api.model_create_multi
    def create(self, vals_list):
        """Create folio windows with the folio's primary payer as the default."""
        for vals in vals_list:
            if not vals.get("partner_id") and vals.get("folio_id"):
                folio = self.env["hospitality.folio"].browse(vals["folio_id"])
                if folio.exists():
                    vals["partner_id"] = folio.partner_id.id
        return super().create(vals_list)
