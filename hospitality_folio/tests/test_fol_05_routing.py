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
FOL-05 — Routing Instruction Model + Evaluator
Tests:
    * test_route_full_percent_to_target_window
    * test_route_with_max_amount_caps_split
    * test_inactive_routing_ignored
    * test_category_filter_matches
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestFol05Routing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create({"name": "Guest FOL-05"})
        cls.currency = cls.env.ref("base.USD")

        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Prop FOL-05"}
            )

        # Transaction codes
        cls.tc_room = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "ROOMCRG")], limit=1
        )
        if not cls.tc_room:
            cls.tc_room = cls.env["hospitality.transaction.code"].create({
                "code": "ROOMCRG_F05",
                "name": "Room Charge F05",
                "transaction_type": "charge",
            })

        cls.tc_fnb = cls.env["hospitality.transaction.code"].create({
            "code": "FNB_F05",
            "name": "F&B Charge F05",
            "transaction_type": "charge",
            "category_filter": "fnb",
        })

    def _make_folio(self):
        folio = self.env["hospitality.folio"].create({
            "property_id": self.property.id,
            "partner_id": self.partner.id,
            "currency_id": self.currency.id,
        })
        folio.action_open_folio()
        # Add window 2 for routing tests
        self.env["hospitality.folio.window"].create({
            "folio_id": folio.id,
            "sequence": 2,
            "label": "F&B",
            "partner_id": self.partner.id,
        })
        return folio

    def _make_rule(self, folio, **kwargs):
        defaults = {
            "name": "Test Rule",
            "category_filter": "all",
            "target_folio_id": folio.id,
            "target_window_seq": 2,
            "percent": 100.0,
            "max_amount": 0.0,
            "active": True,
        }
        defaults.update(kwargs)
        return self.env["hospitality.routing.instruction"].create(defaults)

    # ------------------------------------------------------------------ #
    #  1. Full percent routes to target window                            #
    # ------------------------------------------------------------------ #

    def test_route_full_percent_to_target_window(self):
        """A 100% routing rule sends the full charge amount to window 2."""
        folio = self._make_folio()
        self._make_rule(folio, percent=100.0, target_window_seq=2)

        instructions = self.env["hospitality.routing.instruction"]._evaluate(
            folio=folio,
            transaction_code_id=self.tc_room,
            amount=100.0,
        )

        self.assertEqual(len(instructions), 1)
        self.assertEqual(instructions[0]["target_window_seq"], 2)
        self.assertAlmostEqual(instructions[0]["amount"], 100.0)
        self.assertEqual(instructions[0]["target_folio_id"], folio)

    # ------------------------------------------------------------------ #
    #  2. max_amount caps the routed portion                              #
    # ------------------------------------------------------------------ #

    def test_route_with_max_amount_caps_split(self):
        """max_amount=60 on a 100 USD charge routes 60 to window 2, 40 stays."""
        folio = self._make_folio()
        self._make_rule(
            folio,
            percent=100.0,
            max_amount=60.0,
            target_window_seq=2,
        )

        instructions = self.env["hospitality.routing.instruction"]._evaluate(
            folio=folio,
            transaction_code_id=self.tc_room,
            amount=100.0,
        )

        # Should be two instructions: 60 to window 2, 40 remainder to window 1
        self.assertEqual(len(instructions), 2)
        amounts = {i["target_window_seq"]: i["amount"] for i in instructions}
        self.assertAlmostEqual(amounts.get(2, 0), 60.0)
        self.assertAlmostEqual(amounts.get(1, 0), 40.0)

    # ------------------------------------------------------------------ #
    #  3. Inactive rule is ignored                                        #
    # ------------------------------------------------------------------ #

    def test_inactive_routing_ignored(self):
        """An inactive rule must not affect charge routing."""
        folio = self._make_folio()
        self._make_rule(folio, percent=100.0, target_window_seq=2, active=False)

        instructions = self.env["hospitality.routing.instruction"]._evaluate(
            folio=folio,
            transaction_code_id=self.tc_room,
            amount=100.0,
        )

        # No active rules → default: full amount to window 1
        self.assertEqual(len(instructions), 1)
        self.assertEqual(instructions[0]["target_window_seq"], 1)
        self.assertAlmostEqual(instructions[0]["amount"], 100.0)

    # ------------------------------------------------------------------ #
    #  4. Category filter — fnb charge routed to window 2                #
    # ------------------------------------------------------------------ #

    def test_category_filter_matches(self):
        """An fnb-category rule routes F&B charges to window 2, not room charges."""
        folio = self._make_folio()
        # Rule only matches fnb category
        self._make_rule(
            folio,
            category_filter="fnb",
            target_window_seq=2,
            percent=100.0,
        )

        # F&B charge → should match rule → window 2
        fnb_instrs = self.env["hospitality.routing.instruction"]._evaluate(
            folio=folio,
            transaction_code_id=self.tc_fnb,
            amount=50.0,
        )
        self.assertEqual(len(fnb_instrs), 1)
        self.assertEqual(fnb_instrs[0]["target_window_seq"], 2)

        # Room charge → should NOT match fnb rule → default window 1
        room_instrs = self.env["hospitality.routing.instruction"]._evaluate(
            folio=folio,
            transaction_code_id=self.tc_room,
            amount=100.0,
        )
        self.assertEqual(len(room_instrs), 1)
        self.assertEqual(room_instrs[0]["target_window_seq"], 1)

    # ------------------------------------------------------------------ #
    #  5. Acceptance: F&B charge posts to window 2 via _post_charge      #
    # ------------------------------------------------------------------ #

    def test_fnb_charge_lands_in_window_2_via_post_charge(self):
        """Acceptance test: F&B charge with fnb routing rule lands in window 2."""
        folio = self._make_folio()
        self._make_rule(
            folio,
            category_filter="fnb",
            target_window_seq=2,
            percent=100.0,
        )

        line = folio._post_charge(
            transaction_code_id=self.tc_fnb,
            qty=1,
            price=50.0,
            ref="Test F&B",
        )

        # Ensure we got a single line (or take first if multiple)
        if hasattr(line, '__iter__') and not hasattr(line, 'id'):
            line = line[0]

        win2 = folio.window_ids.filtered(lambda w: w.sequence == 2)
        self.assertTrue(win2, "Window 2 must exist on the folio.")
        self.assertEqual(
            line.window_id,
            win2,
            "F&B charge must land in window 2 when routing rule is active.",
        )

    # ------------------------------------------------------------------ #
    #  6. Constraint: percent must be 0–100                              #
    # ------------------------------------------------------------------ #

    def test_percent_constraint(self):
        """percent outside [0, 100] must raise UserError."""
        folio = self._make_folio()
        with self.assertRaises(UserError):
            self._make_rule(folio, percent=150.0)

    # ------------------------------------------------------------------ #
    #  7. Constraint: max_amount must be >= 0                            #
    # ------------------------------------------------------------------ #

    def test_max_amount_constraint(self):
        """Negative max_amount must raise UserError."""
        folio = self._make_folio()
        with self.assertRaises(UserError):
            self._make_rule(folio, max_amount=-10.0)