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
FOL-04 — Deposits + Allowances
Tests:
    * test_deposit_held_to_applied
    * test_deposit_partial_application
    * test_deposit_refund_creates_negative_line
    * test_allowance_supervisor_only
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


class TestFol04DepositAllowance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_supervisor = cls.env.ref("hospitality_folio.group_folio_supervisor")
        cls.group_cashier = cls.env.ref("hospitality_folio.group_folio_cashier")

        cls.partner = cls.env["res.partner"].create({"name": "Guest FOL-04"})
        cls.currency = cls.env.ref("base.USD")

        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Prop FOL-04"}
            )

        cls.user_cashier = cls.env["res.users"].create({
            "name": "Cashier FOL-04",
            "login": "fol04_cashier@test.com",
            "group_ids": [(6, 0, [
                cls.group_cashier.id,
                cls.env.ref("base.group_user").id,
            ])],
        })
        cls.user_supervisor = cls.env["res.users"].create({
            "name": "Supervisor FOL-04",
            "login": "fol04_super@test.com",
            "group_ids": [(6, 0, [
                cls.group_supervisor.id,
                cls.env.ref("base.group_user").id,
            ])],
        })

        # Transaction codes — use seed data codes from folio_transaction_codes.xml
        cls.tc_room = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "ROOMCRG")], limit=1
        )
        if not cls.tc_room:
            cls.tc_room = cls.env["hospitality.transaction.code"].create({
                "code": "ROOMCRG_F04",
                "name": "Room Charge F04",
                "transaction_type": "charge",
            })

        cls.tc_deposit_in = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "DEPOSIT_IN")], limit=1
        )
        if not cls.tc_deposit_in:
            cls.tc_deposit_in = cls.env["hospitality.transaction.code"].create({
                "code": "DEPOSIT_IN",
                "name": "Deposit Applied",
                "transaction_type": "payment",
            })

        cls.tc_deposit_ref = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "DEPOSIT_REF")], limit=1
        )
        if not cls.tc_deposit_ref:
            cls.tc_deposit_ref = cls.env["hospitality.transaction.code"].create({
                "code": "DEPOSIT_REF",
                "name": "Deposit Refund",
                "transaction_type": "payment",
            })

        cls.tc_allowance = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "ALLOWANCE_1")], limit=1
        )
        if not cls.tc_allowance:
            cls.tc_allowance = cls.env["hospitality.transaction.code"].create({
                "code": "ALLOWANCE_1",
                "name": "Allowance",
                "transaction_type": "adjustment",
                "requires_supervisor": True,
            })

    def _make_folio(self):
        folio = self.env["hospitality.folio"].create({
            "property_id": self.property.id,
            "partner_id": self.partner.id,
            "currency_id": self.currency.id,
        })
        folio.action_open_folio()
        return folio

    def _post_room_charge(self, folio, amount=100.0):
        return self.env["hospitality.folio.line"].create({
            "folio_id": folio.id,
            "transaction_code_id": self.tc_room.id,
            "qty": 1,
            "unit_price": amount,
            "post_date": fields.Date.today(),
            "business_date": fields.Date.today(),
        })

    # ------------------------------------------------------------------ #
    #  1. Deposit held → applied (full)                                   #
    # ------------------------------------------------------------------ #

    def test_deposit_held_to_applied(self):
        """Full deposit application zeroes a matching room charge balance."""
        folio = self._make_folio()
        self._post_room_charge(folio, 100.0)
        self.assertAlmostEqual(folio.balance, 100.0)

        deposit = self.env["hospitality.deposit"].create({
            "folio_id": folio.id,
            "partner_id": self.partner.id,
            "amount": 100.0,
            "currency_id": self.currency.id,
        })
        self.assertEqual(deposit.state, "held")

        deposit.action_apply_to_folio()

        self.assertEqual(deposit.state, "applied")
        self.assertAlmostEqual(deposit.applied_amount, 100.0)
        self.assertAlmostEqual(folio.balance, 0.0)

    # ------------------------------------------------------------------ #
    #  2. Deposit partial application                                      #
    # ------------------------------------------------------------------ #

    def test_deposit_partial_application(self):
        """Applying a deposit for less than its amount → partially_applied."""
        folio = self._make_folio()
        self._post_room_charge(folio, 100.0)

        deposit = self.env["hospitality.deposit"].create({
            "folio_id": folio.id,
            "partner_id": self.partner.id,
            "amount": 100.0,
            "currency_id": self.currency.id,
        })

        deposit.action_apply_to_folio(amount=40.0)

        self.assertEqual(deposit.state, "partially_applied")
        # Balance should be 100 (charge) - 40 (partial apply) = 60
        self.assertAlmostEqual(folio.balance, 60.0)

    # ------------------------------------------------------------------ #
    #  3. Deposit refund creates a credit line                            #
    # ------------------------------------------------------------------ #

    def test_deposit_refund_creates_negative_line(self):
        """Refunding a held deposit creates a folio line and marks state=refunded."""
        folio = self._make_folio()

        deposit = self.env["hospitality.deposit"].create({
            "folio_id": folio.id,
            "partner_id": self.partner.id,
            "amount": 100.0,
            "currency_id": self.currency.id,
        })
        self.assertEqual(deposit.state, "held")

        refund_line = deposit.action_refund()

        self.assertIsNotNone(refund_line, "Refund must return a folio line.")
        self.assertTrue(refund_line.exists(), "Refund line must be persisted.")
        self.assertNotEqual(refund_line.amount_total, 0.0,
                            "Refund line must have non-zero amount.")
        self.assertEqual(deposit.state, "refunded")
        self.assertAlmostEqual(deposit.refunded_amount, 100.0)
        self.assertEqual(deposit.refund_line_id, refund_line)

    # ------------------------------------------------------------------ #
    #  4. Allowance is supervisor-only                                    #
    # ------------------------------------------------------------------ #

    def test_allowance_supervisor_only(self):
        """A cashier must not be able to create an allowance."""
        folio = self._make_folio()
        line = self._post_room_charge(folio, 100.0)

        # Cashier must be blocked.
        with self.assertRaises(AccessError):
            self.env["hospitality.allowance"].with_user(self.user_cashier).create({
                "folio_line_id": line.id,
                "reason": "Test allowance",
                "approved_by": self.user_supervisor.id,
                "amount": -25.0,
            })

        # Supervisor can create.
        allowance = (
            self.env["hospitality.allowance"]
            .with_user(self.user_supervisor)
            .create({
                "folio_line_id": line.id,
                "reason": "Guest complaint resolution",
                "approved_by": self.user_supervisor.id,
                "amount": -25.0,
            })
        )
        self.assertTrue(allowance.exists())
        self.assertEqual(allowance.folio_id, folio)