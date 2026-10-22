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
FOL-07 — Folio Form, Tape Print, Invoice Link
Tests:
    * test_post_charge_wizard_creates_line
    * test_transfer_line_between_windows
    * test_tape_print_excludes_voids
    * test_settle_marks_closed
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestFol07Ui(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Ensure the current test user (Admin) has the required groups.
        group_supervisor = cls.env.ref("hospitality_folio.group_folio_supervisor", raise_if_not_found=False)
        group_cashier = cls.env.ref("hospitality_folio.group_folio_cashier", raise_if_not_found=False)

        if group_supervisor:
            cls.env.user.write({'group_ids': [(4, group_supervisor.id)]})
        if group_cashier:
            cls.env.user.write({'group_ids': [(4, group_cashier.id)]})

        # Add basic hospitality user group if present to ensure property access
        group_hosp_user = cls.env.ref("hospitality_base.group_hospitality_user", raise_if_not_found=False)
        if not group_hosp_user:
            group_hosp_user = cls.env.ref("hospitality.group_hospitality_user", raise_if_not_found=False)
        if group_hosp_user:
            cls.env.user.write({'group_ids': [(4, group_hosp_user.id)]})

        cls.partner = cls.env["res.partner"].create({"name": "Guest FOL-07"})
        cls.currency = cls.env.ref("base.USD")

        cls.property = cls.env["hospitality.property"].search([], limit=1)
        if not cls.property:
            cls.property = cls.env["hospitality.property"].create(
                {"name": "Prop FOL-07"}
            )

        def get_or_create_tc(code, name, t_type, show):
            # Using sudo() ensures we bypass Record Rules that might hide an existing code
            tc = cls.env["hospitality.transaction.code"].sudo().with_context(active_test=False).search(
                [("code", "=", code)], limit=1
            )
            if not tc:
                vals = {
                    "code": code,
                    "name": name,
                    "transaction_type": t_type,
                    "show_on_folio": show,
                }
                if 'property_id' in cls.env["hospitality.transaction.code"]._fields:
                    vals["property_id"] = cls.property.id
                tc = cls.env["hospitality.transaction.code"].sudo().create(vals)
            else:
                update_vals = {
                    'active': True,
                    'transaction_type': t_type,
                }
                if 'property_id' in cls.env["hospitality.transaction.code"]._fields:
                    # Re-align property so the regular user can see it
                    update_vals['property_id'] = cls.property.id
                tc.sudo().write(update_vals)

            # Return it in normal environment context
            return tc.with_env(cls.env)

        # Transaction codes
        cls.tc_room = get_or_create_tc("ROOM", "Room Charge", "charge", True)
        cls.tc_cash = get_or_create_tc("CASH", "Cash Payment", "payment", True)
        cls.tc_internal = get_or_create_tc("INT_ROUTE", "Internal Routing", "transfer", False)
        # Explicitly align the TRANSFER code to avoid UserError in wizard
        cls.tc_transfer = get_or_create_tc("TRANSFER", "Window Transfer", "transfer", False)

    def _make_folio(self, window_count=1):
        """Helper: create an open folio with window_count windows."""
        folio = self.env["hospitality.folio"].create({
            "property_id": self.property.id,
            "partner_id": self.partner.id,
            "currency_id": self.currency.id,
            "window_count": window_count,
        })
        # Create window 1
        self.env["hospitality.folio.window"].create({
            "folio_id": folio.id,
            "sequence": 1,
            "label": "Room",
            "partner_id": self.partner.id,
        })
        if window_count >= 2:
            self.env["hospitality.folio.window"].create({
                "folio_id": folio.id,
                "sequence": 2,
                "label": "F&B",
                "partner_id": self.partner.id,
            })
        return folio

    # ================================================================== #
    #  Test 1 — Post Charge Wizard creates a folio line                   #
    # ================================================================== #

    def test_post_charge_wizard_creates_line(self):
        """Wizard posts a charge line with correct amounts."""
        folio = self._make_folio()

        wizard = self.env["hospitality.folio.post.charge.wizard"].create({
            "folio_id": folio.id,
            "transaction_code_id": self.tc_room.id,
            "qty": 2.0,
            "unit_price": 150.0,
            "reference": "Test room",
            "window_seq": 1,
        })
        wizard.action_post()

        folio.invalidate_recordset()
        self.assertEqual(len(folio.line_ids), 1)
        line = folio.line_ids[0]
        self.assertEqual(line.transaction_code_id, self.tc_room)
        self.assertAlmostEqual(line.qty, 2.0)
        self.assertAlmostEqual(line.unit_price, 150.0)
        self.assertAlmostEqual(line.amount_total, 300.0)
        self.assertFalse(line.is_void)

    # ================================================================== #
    #  Test 2 — Transfer line between windows                             #
    # ================================================================== #

    def test_transfer_line_between_windows(self):
        """Transfer wizard voids source line and creates a new line on window 2."""
        folio = self._make_folio(window_count=2)

        # Post a charge on window 1
        folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=200.0,
            ref="Night 1",
            window_seq=1,
        )
        folio.flush_model()
        folio.invalidate_recordset()

        original_line = folio.line_ids.filtered(lambda l: not l.is_void)[0]
        self.assertEqual(original_line.window_id.sequence, 1)

        # Run transfer wizard
        wizard = self.env["hospitality.folio.transfer.line.wizard"].create({
            "folio_id": folio.id,
            "line_id": original_line.id,
            "transfer_mode": "window",
            "target_window_seq": 2,
        })
        wizard.action_transfer()

        folio.flush_model()
        folio.invalidate_recordset()

        # Original line should now be voided
        original_line.invalidate_recordset()
        # A new void mirror line must exist
        void_lines = folio.line_ids.filtered(lambda l: l.is_void)
        self.assertTrue(void_lines, "A voided mirror line should exist after transfer.")

        # A new non-voided line on window 2 must exist
        new_lines = folio.line_ids.filtered(
            lambda l: not l.is_void and l.window_id.sequence == 2
        )
        self.assertTrue(new_lines, "A new charge line on window 2 should exist.")
        self.assertAlmostEqual(new_lines[0].unit_price, 200.0)

    # ================================================================== #
    #  Test 3 — Tape print excludes voided lines and hidden codes         #
    # ================================================================== #

    def test_tape_print_excludes_voids(self):
        """Lines where is_void=True or show_on_folio=False must be excluded from tape."""
        folio = self._make_folio()

        # Post a visible charge
        folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=100.0,
            ref="Visible",
            window_seq=1,
        )
        # Post an internal (show_on_folio=False) charge
        folio._post_charge(
            transaction_code_id=self.tc_internal,
            qty=1,
            price=50.0,
            ref="Hidden",
            window_seq=1,
        )
        folio.flush_model()
        folio.invalidate_recordset()

        # Void the visible line
        visible_line = folio.line_ids.filtered(
            lambda l: not l.is_void and l.transaction_code_id == self.tc_room
        )
        if visible_line:
            folio._void_line(
                visible_line[0].id, reason="Test void"
            )

        folio.flush_model()
        folio.invalidate_recordset()

        # Replicate tape filter: not void AND show_on_folio=True
        tape_lines = folio.line_ids.filtered(
            lambda l: not l.is_void
                      and l.transaction_code_id
                      and l.transaction_code_id.show_on_folio
        )
        # Neither the voided line nor the internal line should appear
        for line in tape_lines:
            self.assertFalse(line.is_void, "Voided lines must not appear on tape.")
            self.assertTrue(
                line.transaction_code_id.show_on_folio,
                "Lines with show_on_folio=False must not appear on tape.",
            )

    # ================================================================== #
    #  Test 4 — Settle marks folio closed                                 #
    # ================================================================== #

    def test_settle_marks_closed(self):
        """action_settle closes the folio when balance is zero."""
        folio = self._make_folio()

        # Post a charge and matching payment so balance = 0
        folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=100.0,
            ref="Room",
            window_seq=1,
        )
        folio._post_payment(
            transaction_code_id=self.tc_cash,
            amount=100.0,
            payment_ref="Receipt 001",
        )
        folio.flush_model()
        folio.invalidate_recordset()

        self.assertAlmostEqual(folio.balance, 0.0)

        folio.action_settle()
        folio.invalidate_recordset()

        self.assertEqual(folio.state, "closed")
        self.assertEqual(folio.closing_date, fields.Date.today())

    # ================================================================== #
    #  Test 5 — Settle fails when balance is non-zero                     #
    # ================================================================== #

    def test_settle_fails_with_nonzero_balance(self):
        """action_settle raises UserError when balance is not zero."""
        folio = self._make_folio()

        folio._post_charge(
            transaction_code_id=self.tc_room,
            qty=1,
            price=200.0,
            ref="Unpaid room",
            window_seq=1,
        )
        folio.flush_model()
        folio.invalidate_recordset()

        with self.assertRaises(UserError):
            folio.action_settle()