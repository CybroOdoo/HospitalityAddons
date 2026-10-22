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
FOL-06 — AR Account + City Ledger
Tests:
    * test_transfer_to_ar_creates_line
    * test_balance_computed_from_open_lines
    * test_partial_payment_updates_line_state
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestFol06Ar(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.group_supervisor = cls.env.ref(
            "hospitality_folio.group_folio_supervisor"
        )

        cls.partner = cls.env["res.partner"].create({"name": "Guest FOL-06"})
        cls.currency = cls.env.ref("base.USD")

        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Prop FOL-06"}
            )

        # Supervisor user required for AR transfer
        cls.user_supervisor = cls.env["res.users"].create({
            "name": "Supervisor FOL-06",
            "login": "fol06_supervisor@test.com",
            "group_ids": [(6, 0, [
                cls.group_supervisor.id,
                cls.env.ref("base.group_user").id,
            ])],
        })

        # Transaction codes needed by _post_charge / _post_payment
        cls.tc_room = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "ROOMCRG")], limit=1
        )
        if not cls.tc_room:
            cls.tc_room = cls.env["hospitality.transaction.code"].create({
                "code": "ROOMCRG_F06",
                "name": "Room Charge F06",
                "transaction_type": "charge",
            })

        cls.tc_payment = cls.env["hospitality.transaction.code"].search(
            [("code", "=", "CASH")], limit=1
        )
        if not cls.tc_payment:
            cls.tc_payment = cls.env["hospitality.transaction.code"].create({
                "code": "CASH_F06",
                "name": "Cash Payment F06",
                "transaction_type": "payment",
            })

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _make_folio(self, balance_amount=200.0):
        """Create an open folio with a single charge line."""
        folio = self.env["hospitality.folio"].create({
            "property_id": self.property.id,
            "partner_id": self.partner.id,
            "currency_id": self.currency.id,
        })
        folio.action_open_folio()
        # Post a charge so the folio has a positive balance
        folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=balance_amount,
            ref="Room charge FOL-06",
        )
        return folio

    def _make_ar_account(self):
        return self.env["hospitality.ar.account"].create({
            "partner_id": self.partner.id,
            "property_id": self.property.id,
            "currency_id": self.currency.id,
        })

    # ================================================================== #
    #  1. Transferring a folio to AR creates an open AR line              #
    # ================================================================== #

    def test_transfer_to_ar_creates_line(self):
        """Acceptance: transferring a 200 USD folio to AR creates an open
        AR line of 200 USD on the partner's account.
        """
        folio = self._make_folio(balance_amount=200.0)
        self.assertAlmostEqual(folio.balance, 200.0,
                               msg="Folio must have 200 USD balance before transfer.")

        # action_transfer_to_ar is supervisor-gated via groups in the view;
        # the method itself checks balance > 0. Call as supervisor.
        folio_sudo = folio.with_user(self.user_supervisor)
        folio_sudo.action_transfer_to_ar()

        self.assertEqual(folio.state, "transferred_ar",
                         "Folio state must be 'transferred_ar' after transfer.")

        # Locate the AR account created for this partner+property
        ar_account = self.env["hospitality.ar.account"].search([
            ("partner_id", "=", self.partner.id),
            ("property_id", "=", self.property.id),
        ], limit=1)
        self.assertTrue(ar_account,
                        "An AR account must exist for the partner after transfer.")

        ar_lines = ar_account.line_ids.filtered(
            lambda l: l.folio_id.id == folio.id
        )
        self.assertEqual(len(ar_lines), 1,
                         "Exactly one AR line must be created for the transferred folio.")
        ar_line = ar_lines[0]
        self.assertAlmostEqual(ar_line.amount, 200.0,
                               msg="AR line amount must equal the transferred balance.")
        self.assertEqual(ar_line.state, "open",
                         "Newly created AR line must be in 'open' state.")

    # ================================================================== #
    #  2. Balance is computed from open AR lines                          #
    # ================================================================== #

    def test_balance_computed_from_open_lines(self):
        """AR account balance equals the sum of (amount − paid_amount)
        across open and partially-paid lines only.
        """
        account = self._make_ar_account()
        today = fields.Date.today()

        # Three lines: open 100, partial 60/150, paid 80/80
        line_open = self.env["hospitality.ar.line"].create({
            "account_id": account.id,
            "amount": 100.0,
            "currency_id": self.currency.id,
            "due_date": today,
        })
        line_partial = self.env["hospitality.ar.line"].create({
            "account_id": account.id,
            "amount": 150.0,
            "paid_amount": 60.0,
            "currency_id": self.currency.id,
            "due_date": today,
        })
        line_paid = self.env["hospitality.ar.line"].create({
            "account_id": account.id,
            "amount": 80.0,
            "paid_amount": 80.0,
            "currency_id": self.currency.id,
            "due_date": today,
        })

        account._compute_balance()

        # open: 100, partial: 90 outstanding, paid: excluded → total 190
        self.assertAlmostEqual(
            account.balance, 190.0,
            msg="Balance must be 100 (open) + 90 (partial outstanding) = 190.",
        )

        # Verify states were auto-assigned
        self.assertEqual(line_open.state, "open")
        self.assertEqual(line_partial.state, "partial")
        self.assertEqual(line_paid.state, "paid")

    # ================================================================== #
    #  3. Partial payment updates AR line state correctly                 #
    # ================================================================== #

    def test_partial_payment_updates_line_state(self):
        """Posting a partial payment transitions state open → partial,
        and full payment transitions partial → paid.
        """
        account = self._make_ar_account()
        today = fields.Date.today()

        line = self.env["hospitality.ar.line"].create({
            "account_id": account.id,
            "amount": 200.0,
            "currency_id": self.currency.id,
            "due_date": today,
        })
        self.assertEqual(line.state, "open")

        # Partial payment: 120
        line.action_post_payment(120.0)
        self.assertEqual(line.state, "partial",
                         "State must be 'partial' after paying 120/200.")
        self.assertAlmostEqual(line.paid_amount, 120.0)
        self.assertAlmostEqual(line.outstanding, 80.0)

        # Full payment: remaining 80
        line.action_post_payment(80.0)
        self.assertEqual(line.state, "paid",
                         "State must be 'paid' after full payment.")
        self.assertAlmostEqual(line.paid_amount, 200.0)
        self.assertAlmostEqual(line.outstanding, 0.0)

        # Further payment must raise
        with self.assertRaises(UserError):
            line.action_post_payment(1.0)

    # ================================================================== #
    #  4. _get_or_create_for_partner returns existing open account        #
    # ================================================================== #

    def test_get_or_create_reuses_existing_account(self):
        """_get_or_create_for_partner must not create duplicate accounts."""
        account1 = self.env["hospitality.ar.account"]._get_or_create_for_partner(
            self.partner, self.property, self.currency
        )
        account2 = self.env["hospitality.ar.account"]._get_or_create_for_partner(
            self.partner, self.property, self.currency
        )
        self.assertEqual(account1, account2,
                         "Must reuse existing open AR account, not create a new one.")

    # ================================================================== #
    #  5. AR line amount must be positive                                 #
    # ================================================================== #

    def test_ar_line_amount_must_be_positive(self):
        """Creating an AR line with amount <= 0 must raise UserError."""
        account = self._make_ar_account()
        with self.assertRaises(UserError):
            self.env["hospitality.ar.line"].create({
                "account_id": account.id,
                "amount": 0.0,
                "currency_id": self.currency.id,
                "due_date": fields.Date.today(),
            })