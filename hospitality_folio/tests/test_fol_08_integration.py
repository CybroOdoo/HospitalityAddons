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
FOL-08 — Integration Tests

Three end-to-end scenarios that exercise the full folio lifecycle:

    test_integration_room_post_at_checkin_and_settle_at_checkout
        Simulates check-in → nightly room postings → checkout settlement.
        Verifies that balance reaches zero after payments match charges.

    test_integration_routed_fnb_lands_in_correct_window
        Verifies that an F&B charge with an active fnb→window-2 routing
        rule lands in window 2 (guest payer) while ROOM charges stay in
        window 1 (company payer).

    test_integration_transfer_to_ar_when_company_pays_later
        Simulates a corporate account where the room charge is transferred
        to AR (deferred payment), an AR line is created, and the folio
        moves to transferred_ar state.
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestFol08Integration(TransactionCase):
    """FOL-08 integration test bundle — full lifecycle scenarios."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Shared property ──────────────────────────────────────────
        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Prop FOL-08"}
            )

        cls.currency = cls.env.ref("base.USD")

        # ── Partners ─────────────────────────────────────────────────
        cls.guest_partner = cls.env["res.partner"].create(
            {"name": "Integration Guest FOL-08"}
        )
        cls.company_partner = cls.env["res.partner"].create(
            {"name": "Integration Corp FOL-08", "is_company": True}
        )

        # ── Transaction codes ─────────────────────────────────────────
        cls.tc_room = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "ROOMCRG")], limit=1
        )
        if not cls.tc_room:
            cls.tc_room = cls.env["hospitality.transaction.code"].create({
                "code": "ROOMCRG_F08",
                "name": "Room Charge F08",
                "transaction_type": "charge",
                "category": "room",
            })

        # Always use a dedicated code with category_filter="fnb" so routing
        # rules that filter on the "fnb" category reliably match.
        # The shared FB code has category_filter="all" and would not match.
        cls.tc_fnb = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "FB_F08")], limit=1
        )
        if not cls.tc_fnb:
            cls.tc_fnb = cls.env["hospitality.transaction.code"].create({
                "code": "FB_F08",
                "name": "F&B Charge F08",
                "transaction_type": "charge",
                "category_filter": "fnb",
            })

        cls.tc_cash = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "CASH")], limit=1
        )
        if not cls.tc_cash:
            cls.tc_cash = cls.env["hospitality.transaction.code"].create({
                "code": "CASH_F08",
                "name": "Cash Payment F08",
                "transaction_type": "payment",
            })

        cls.tc_cc = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "CC")], limit=1
        )
        if not cls.tc_cc:
            cls.tc_cc = cls.env["hospitality.transaction.code"].create({
                "code": "CC_F08",
                "name": "Credit Card F08",
                "transaction_type": "payment",
            })

        # ── Supervisor group (needed for AR transfer) ─────────────────
        cls.group_supervisor = cls.env.ref(
            "hospitality_folio.group_folio_supervisor"
        )
        cls.supervisor_user = cls.env["res.users"].create({
            "name": "Supervisor FOL-08",
            "login": "fol08_supervisor@test.integration",
            "group_ids": [(6, 0, [
                cls.group_supervisor.id,
                cls.env.ref("base.group_user").id,
            ])],
        })

    # ================================================================ #
    #  Helpers                                                          #
    # ================================================================ #

    def _make_folio(self, partner=None, windows=1):
        """Return an open folio with `windows` billing windows."""
        partner = partner or self.guest_partner
        folio = self.env["hospitality.folio"].create({
            "property_id": self.property.id,
            "partner_id": partner.id,
            "currency_id": self.currency.id,
            "window_count": windows,
        })
        folio.action_open_folio()
        return folio

    def _add_window(self, folio, seq, label, partner=None):
        partner = partner or folio.partner_id
        return self.env["hospitality.folio.window"].create({
            "folio_id": folio.id,
            "sequence": seq,
            "label": label,
            "partner_id": partner.id,
        })

    def _post_room(self, folio, nights=1, rate=150.0):
        lines = self.env["hospitality.folio.line"]
        for n in range(nights):
            lines |= folio._post_charge(
                transaction_code_id=self.tc_room,
                qty=1,
                price=rate,
                ref=f"Room night {n + 1}",
            )
        return lines

    def _post_fnb(self, folio, amount=80.0):
        return folio._post_charge(
            transaction_code_id=self.tc_fnb,
            qty=1,
            price=amount,
            ref="Restaurant charge",
        )

    def _post_payment(self, folio, amount):
        return folio._post_payment(
            transaction_code_id=self.tc_cash,
            amount=amount,
            payment_ref="Settlement",
        )

    # ================================================================ #
    #  1. Room post at check-in → settle at checkout                   #
    # ================================================================ #

    def test_integration_room_post_at_checkin_and_settle_at_checkout(self):
        """
        Full check-in / nightly posting / checkout flow:

        1. Create folio (simulates check-in).
        2. Post 3 ROOM charges of 150 USD each (nightly audit run).
        3. Post 1 F&B charge of 75 USD.
        4. Verify total_charges == 525 (450 ROOM + 75 F&B).
        5. Post payment of 525 USD.
        6. Verify balance == 0.
        7. Call action_settle → state becomes 'closed'.
        """
        folio = self._make_folio()

        # Step 2 — 3 nightly room charges
        self._post_room(folio, nights=3, rate=150.0)

        # Step 3 — F&B
        self._post_fnb(folio, amount=75.0)

        # Step 4 — charges total
        self.assertAlmostEqual(
            folio.total_charges,
            525.0,
            places=2,
            msg="Total charges must be 525 USD (450 ROOM + 75 F&B).",
        )

        # Step 5 — settle
        self._post_payment(folio, amount=525.0)

        # Step 6 — zero balance
        self.assertAlmostEqual(
            folio.balance,
            0.0,
            places=2,
            msg="Balance must be zero after full payment.",
        )

        # Step 7 — close
        folio.action_settle()
        self.assertEqual(
            folio.state,
            "closed",
            "Folio must be in 'closed' state after action_settle.",
        )
        self.assertEqual(
            folio.closing_date,
            fields.Date.today(),
            "closing_date must be set to today on settle.",
        )

    # ================================================================ #
    #  2. Routed F&B lands in correct window                           #
    # ================================================================ #

    def test_integration_routed_fnb_lands_in_correct_window(self):
        """
        Folio with two windows:
            Window 1 — ROOM → company payer
            Window 2 — F&B  → guest payer

        Routing rule: F&B category → window 2 (100 %).

        Assertions:
        - ROOM charge line has window_id.sequence == 1.
        - F&B charge line has window_id.sequence == 2.
        - Window 2 payer is guest_partner.
        """
        folio = self._make_folio(partner=self.company_partner)

        # window 1 already exists (created by action_open_folio)
        win1 = folio.window_ids.filtered(lambda w: w.sequence == 1)
        self.assertTrue(win1, "Window 1 must exist after action_open_folio.")
        # Update window 1 payer to company
        win1.partner_id = self.company_partner

        # Add window 2 for F&B / guest
        win2 = self._add_window(folio, seq=2, label="F&B (Guest)",
                                partner=self.guest_partner)

        # Routing rule: fnb → window 2
        self.env["hospitality.routing.instruction"].create({
            "name": "F&B to Guest Window",
            "sequence": 10,
            "active": True,
            "category_filter": "fnb",
            "target_folio_id": folio.id,
            "target_window_id": win2.id,
            "target_window_seq": 2,
            "percent": 100.0,
            "max_amount": 0.0,
        })

        # Post ROOM — should use default routing (window 1)
        room_line = folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=200.0,
            ref="Room night 1",
        )

        # Post F&B — routing rule should redirect to window 2
        fnb_line = folio._post_charge(
            transaction_code_id=self.tc_fnb,
            qty=2,
            price=45.0,
            ref="Restaurant dinner",
        )

        # Normalise: _post_charge may return single record or recordset
        if hasattr(room_line, "__iter__") and not hasattr(room_line, "window_id"):
            room_line = room_line[0]
        if hasattr(fnb_line, "__iter__") and not hasattr(fnb_line, "window_id"):
            fnb_line = fnb_line[0]

        self.assertEqual(
            room_line.window_id.sequence,
            1,
            "ROOM charge must land in window 1 (company).",
        )
        self.assertEqual(
            fnb_line.window_id.sequence,
            2,
            "F&B charge must be routed to window 2 (guest) by the routing rule.",
        )
        self.assertEqual(
            fnb_line.window_id.partner_id,
            self.guest_partner,
            "Window 2 payer must be the guest partner.",
        )

        # Amounts
        self.assertAlmostEqual(room_line.amount_total, 200.0, places=2)
        self.assertAlmostEqual(fnb_line.amount_total, 90.0, places=2)

    # ================================================================ #
    #  3. Transfer to AR when company pays later                       #
    # ================================================================ #

    def test_integration_transfer_to_ar_when_company_pays_later(self):
        """
        Corporate direct-billing scenario:

        1. Folio for a corporate guest (company payer).
        2. Post ROOM charges totalling 400 USD.
        3. Transfer the open balance to AR (city ledger).
        4. Verify:
            - folio.state == 'transferred_ar'
            - An AR line of 400 USD is created for the company partner.
            - AR account balance reflects the transfer.
        """
        folio = self._make_folio(partner=self.company_partner)

        # Step 2 — room charges
        self._post_room(folio, nights=2, rate=200.0)
        self.assertAlmostEqual(folio.balance, 400.0, places=2)

        # Step 3 — transfer to AR (runs as supervisor so no access error)
        folio.with_user(self.supervisor_user).action_transfer_to_ar()

        # Step 4a — folio state
        self.assertEqual(
            folio.state,
            "transferred_ar",
            "Folio must move to 'transferred_ar' state after AR transfer.",
        )

        # Step 4b — AR line exists with correct amount
        ar_lines = self.env["hospitality.ar.line"].search([
            ("folio_id", "=", folio.id),
        ])
        self.assertTrue(ar_lines, "An AR line must be created on transfer.")
        self.assertAlmostEqual(
            sum(ar_lines.mapped("amount")),
            400.0,
            places=2,
            msg="AR line(s) must sum to 400 USD (the transferred balance).",
        )

        # Step 4c — AR account exists for the company partner
        ar_account = self.env["hospitality.ar.account"].search([
            ("partner_id", "=", self.company_partner.id),
            ("property_id", "=", self.property.id),
        ], limit=1)
        self.assertTrue(
            ar_account,
            "An AR account must exist for the company partner after transfer.",
        )
        # AR account balance should reflect the open line
        self.assertGreater(
            ar_account.balance,
            0.0,
            "AR account balance must be positive after transfer.",
        )

        # Step 4d — folio can no longer accept new charge lines
        with self.assertRaises(UserError):
            folio._post_charge(
                transaction_code_id=self.tc_room,
                qty=1,
                price=50.0,
                ref="Should fail — folio closed",
            )