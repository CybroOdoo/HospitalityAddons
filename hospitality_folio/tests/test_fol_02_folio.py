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
FOL-02 — Folio + Window models + State Machine
Tests:
    * test_open_folio_creates_window_1
    * test_settle_requires_zero_balance
    * test_write_off_supervisor_only
    * test_dispute_freeze_then_resume
    * test_window_count_within_bounds
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestFol02FolioStateMachine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_user = cls.env.ref("base.group_user")
        cls.group_cashier = cls.env.ref("hospitality_folio.group_folio_cashier")
        cls.group_supervisor = cls.env.ref("hospitality_folio.group_folio_supervisor")

        cls.partner = cls.env["res.partner"].create({"name": "Test Guest FOL-02"})
        cls.currency = cls.env.ref("base.USD")

        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Test Property FOL-02"}
            )

        cls.user_cashier = cls._make_user("fol02_cashier", cls.group_cashier)
        cls.user_supervisor = cls._make_user("fol02_supervisor", cls.group_supervisor)

    @classmethod
    def _make_user(cls, login, group):
        return cls.env["res.users"].create({
            "name": login,
            "login": login + "@test.folio",
            "group_ids": [(6, 0, [group.id, cls.env.ref("base.group_user").id])],
        })

    def _make_folio(self, **extra):
        vals = {
            "property_id": self.property.id,
            "partner_id": self.partner.id,
            "currency_id": self.currency.id,
        }
        vals.update(extra)
        return self.env["hospitality.folio"].create(vals)

    # ------------------------------------------------------------------ #
    #  1. action_open_folio creates window 1                              #
    # ------------------------------------------------------------------ #

    def test_open_folio_creates_window_1(self):
        folio = self._make_folio()
        self.assertEqual(folio.state, "open")
        self.assertFalse(folio.window_ids)

        folio.action_open_folio()

        win1 = folio.window_ids.filtered(lambda w: w.sequence == 1)
        self.assertTrue(win1, "Window with sequence=1 must exist after action_open_folio.")
        self.assertEqual(win1.partner_id, self.partner)

    def test_open_folio_idempotent(self):
        folio = self._make_folio()
        folio.action_open_folio()
        folio.action_open_folio()
        win1_count = len(folio.window_ids.filtered(lambda w: w.sequence == 1))
        self.assertEqual(win1_count, 1, "Window 1 must not be duplicated.")

    # ------------------------------------------------------------------ #
    #  2. action_settle requires zero balance                             #
    # ------------------------------------------------------------------ #

    def test_settle_requires_zero_balance(self):
        """action_settle must raise UserError when balance != 0."""
        folio = self._make_folio()
        tc = self.env["hospitality.transaction.code"].create({
            "code": "SETTLE_TEST",
            "name": "Settle Test Charge",
            "transaction_type": "charge",
        })
        self.env["hospitality.folio.line"].create({
            "folio_id": folio.id,
            "transaction_code_id": tc.id,
            "qty": 1,
            "unit_price": 150.0,
            "post_date": fields.Date.today(),
            "business_date": fields.Date.today(),
        })
        folio.invalidate_recordset()
        self.assertAlmostEqual(folio.balance, 150.0)

        with self.assertRaises(UserError, msg="Settle must fail when balance > 0."):
            folio.action_settle()

    def test_settle_succeeds_on_zero_balance(self):
        folio = self._make_folio()
        folio.action_settle()
        self.assertEqual(folio.state, "closed")
        self.assertTrue(folio.closing_date)

    # ------------------------------------------------------------------ #
    #  3. action_write_off is supervisor-only                             #
    # ------------------------------------------------------------------ #

    def test_write_off_supervisor_only(self):
        folio = self._make_folio()
        with self.assertRaises(UserError):
            folio.with_user(self.user_cashier).action_write_off()

    def test_write_off_allowed_for_supervisor(self):
        folio = self._make_folio()
        folio.with_user(self.user_supervisor).action_write_off()
        self.assertEqual(folio.state, "written_off")

    # ------------------------------------------------------------------ #
    #  4. Dispute: open → in_dispute → open                              #
    # ------------------------------------------------------------------ #

    def test_dispute_freeze_then_resume(self):
        folio = self._make_folio()
        folio.action_dispute()
        self.assertEqual(folio.state, "in_dispute")
        folio.action_resolve_dispute()
        self.assertEqual(folio.state, "open")

    def test_dispute_from_non_open_raises(self):
        folio = self._make_folio()
        folio.action_settle()
        with self.assertRaises(UserError):
            folio.action_dispute()

    # ------------------------------------------------------------------ #
    #  5. window_count within bounds (1–8)                               #
    # ------------------------------------------------------------------ #

    def test_window_count_within_bounds(self):
        folio = self._make_folio()
        with self.assertRaises(UserError):
            folio.write({"window_count": 0})
        with self.assertRaises(UserError):
            folio.write({"window_count": 9})

    def test_window_count_valid_boundaries(self):
        folio = self._make_folio()
        folio.write({"window_count": 1})
        folio._check_window_count()
        folio.write({"window_count": 8})
        folio._check_window_count()

    # ------------------------------------------------------------------ #
    #  6. Cannot delete folio with lines (structural guard)              #
    # ------------------------------------------------------------------ #

    def test_folio_without_lines_can_be_deleted(self):
        folio = self._make_folio()
        folio_id = folio.id
        folio.unlink()
        self.assertFalse(
            self.env["hospitality.folio"].browse(folio_id).exists()
        )

    # ------------------------------------------------------------------ #
    #  7. Window unique-sequence constraint                               #
    # ------------------------------------------------------------------ #

    def test_window_sequence_unique_per_folio(self):
        folio = self._make_folio()
        self.env["hospitality.folio.window"].create(
            {"folio_id": folio.id, "sequence": 1, "label": "Room"}
        )
        with self.assertRaises(UserError):
            self.env["hospitality.folio.window"].create(
                {"folio_id": folio.id, "sequence": 1, "label": "Duplicate"}
            )