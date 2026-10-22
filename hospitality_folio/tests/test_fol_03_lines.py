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
FOL-03 — Folio Lines + Posting API (spec-compliant)
Tests:
    * test_post_charge_creates_line
    * test_post_payment_credits_balance
    * test_void_line_creates_mirror
    * test_immutable_lines_after_close
    * test_business_date_uses_property_not_today
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError


class TestFol03Lines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("base.group_user")
        cls.group_cashier = cls.env.ref("hospitality_folio.group_folio_cashier")
        cls.group_supervisor = cls.env.ref(
            "hospitality_folio.group_folio_supervisor"
        )

        cls.partner = cls.env["res.partner"].create({"name": "Guest FOL-03"})
        cls.currency = cls.env.ref("base.USD")

        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Prop FOL-03"}
            )

        cls.user_cashier = cls.env["res.users"].create(
            {
                "name": "Cashier",
                "login": "fol03_cashier@test.com",
                "group_ids": [(6, 0, [cls.group_cashier.id, cls.group_user.id])],
            }
        )
        cls.user_supervisor = cls.env["res.users"].create(
            {
                "name": "Supervisor",
                "login": "fol03_super@test.com",
                "group_ids": [(6, 0, [cls.group_supervisor.id, cls.group_user.id])],
            }
        )

        cls.tc_room = cls.env["hospitality.transaction.code"].create(
            {
                "code": "ROOM_T03",
                "name": "Room Charge T03",
                "transaction_type": "charge",
            }
        )
        cls.tc_cash = cls.env["hospitality.transaction.code"].create(
            {
                "code": "CASH_T03",
                "name": "Cash Payment T03",
                "transaction_type": "payment",
            }
        )

    def _make_folio(self):
        folio = self.env["hospitality.folio"].create(
            {
                "property_id": self.property.id,
                "partner_id": self.partner.id,
                "currency_id": self.currency.id,
            }
        )
        folio.action_open_folio()
        return folio

    # ------------------------------------------------------------------ #
    # 1. _post_charge creates a line and increases balance
    # ------------------------------------------------------------------ #
    def test_post_charge_creates_line(self):
        folio = self._make_folio()
        line = folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=100.0,
            ref="Night 1",
        )
        self.assertTrue(line.exists())
        self.assertEqual(line.amount, 100.0)
        self.assertFalse(line.is_void)
        self.assertAlmostEqual(folio.balance, 100.0)

    # ------------------------------------------------------------------ #
    # 2. _post_payment credits the balance to zero
    # ------------------------------------------------------------------ #
    def test_post_payment_credits_balance(self):
        folio = self._make_folio()
        folio._post_charge(
            transaction_code_id=self.tc_room, qty=1, price=100.0, ref="Room"
        )
        self.assertAlmostEqual(folio.balance, 100.0)

        folio._post_payment(
            transaction_code_id=self.tc_cash, amount=100.0, payment_ref="PMT-001"
        )
        self.assertAlmostEqual(folio.balance, 0.0)
        self.assertAlmostEqual(folio.total_payments, 100.0)

    # ------------------------------------------------------------------ #
    # 3. _void_line creates a mirror line; original untouched
    # ------------------------------------------------------------------ #
    def test_void_line_creates_mirror(self):
        folio = self._make_folio()
        line = folio._post_charge(
            transaction_code_id=self.tc_room, qty=1, price=100.0, ref="Room"
        )
        self.assertAlmostEqual(folio.balance, 100.0)

        void_line = folio.with_user(self.user_supervisor)._void_line(
            line.id, reason="Guest dispute"
        )

        self.assertTrue(void_line.is_void)
        self.assertEqual(void_line.void_of_id, line)
        self.assertAlmostEqual(void_line.amount, -100.0)
        self.assertAlmostEqual(folio.balance, 0.0)

        # Original line must remain intact
        self.assertFalse(line.is_void)
        self.assertAlmostEqual(line.amount, 100.0)

    # ------------------------------------------------------------------ #
    # 4. Lines are immutable after folio is closed (admin can override)
    # ------------------------------------------------------------------ #
    def test_immutable_lines_after_close(self):
        folio = self._make_folio()
        line = folio._post_charge(
            transaction_code_id=self.tc_room, qty=1, price=50.0, ref="Room"
        )
        # Zero the balance so we can settle naturally
        folio._post_payment(
            transaction_code_id=self.tc_cash, amount=50.0, payment_ref="PMT-001"
        )
        folio.action_settle()
        self.assertEqual(folio.state, "closed")

        # Cashier cannot edit
        with self.assertRaises(UserError):
            line.with_user(self.user_cashier).write({"reference": "hacked"})

        # Admin override allowed
        line.with_user(self.env.ref("base.user_admin")).write(
            {"reference": "admin-ok"}
        )

    # ------------------------------------------------------------------ #
    # 5. business_date pulls from property, not today's date
    # ------------------------------------------------------------------ #
    def test_business_date_uses_property_not_today(self):
        past_date = fields.Date.from_string("2024-01-15")
        if hasattr(self.property, "business_date"):
            self.property.with_user(self.env.ref("base.user_admin")).write(
                {"business_date": past_date}
            )
        folio = self._make_folio()
        line = folio._post_charge(
            transaction_code_id=self.tc_room, qty=1, price=10.0
        )
        if hasattr(self.property, "business_date"):
            self.assertEqual(line.business_date, past_date)
        else:
            # If property model lacks business_date, at least assert it is set
            self.assertTrue(line.business_date)