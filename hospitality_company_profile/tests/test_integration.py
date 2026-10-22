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
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestIntegration(TransactionCase):
    """COMP-06 integration tests — cross-feature scenarios."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Contract = cls.env['hospitality.contract']
        cls.Wizard = cls.env['hospitality.contract.terminate.wizard']
        cls.Move = cls.env['account.move']

    # ── helpers ───────────────────────────────────────────────────────────────

    def _make_corporate_partner(self, name, credit_limit=10000.0):
        """Create a corporate partner with a given credit limit."""
        return self.Partner.create({
            'name': name,
            'is_corporate_account': True,
            'hospitality_credit_limit': credit_limit,
            'company_type': 'company',
        })

    def _make_contract(self, partner, name, code,
                       start_offset=0, end_offset=365, discount=0.0):
        """Create a contract in draft state."""
        today = fields.Date.today()
        return self.Contract.create({
            'name': name,
            'code': code,
            'partner_id': partner.id,
            'start_date': today + timedelta(days=start_offset),
            'end_date': today + timedelta(days=end_offset),
            'discount_pct': discount,
        })

    def _post_invoice(self, partner, amount):
        """Create and post an unpaid customer invoice for the given amount."""
        move = self.Move.create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': 'Room Charge',
                'quantity': 1,
                'price_unit': amount,
            })],
        })
        move.action_post()
        return move

    def _refresh_credit(self, partner):
        """Force recompute of credit_used/credit_status (mimics cron)."""
        partner._compute_credit_used()
        partner._compute_credit_status()

    # ── test_integration_invoice_pushes_partner_to_near_limit ─────────────────

    def test_integration_invoice_pushes_partner_to_near_limit(self):
        """
        Scenario: a corporate partner with a credit limit receives an invoice
        large enough to push their balance into the 'near_limit' band.

        Steps
        -----
        1. Create corporate partner with credit_limit = 10,000.
        2. Confirm credit_status starts as 'ok'.
        3. Post an invoice for 8,500 (85% of limit).
        4. Recompute credit (mimics daily cron).
        5. Assert credit_used == 8,500 and credit_status == 'near_limit'.
        6. Post a second invoice for 2,000, pushing total to 10,500.
        7. Recompute and assert credit_status == 'exceeded'.
        """
        partner = self._make_corporate_partner(
            'Integration Credit Partner', credit_limit=10000.0
        )

        # Step 2 — baseline
        self._refresh_credit(partner)
        self.assertEqual(partner.credit_status, 'ok',
            "New partner with no invoices should be 'ok'.")

        # Step 3 & 4 — push to near_limit
        self._post_invoice(partner, 8500.0)
        self._refresh_credit(partner)

        self.assertAlmostEqual(partner.credit_used, 8500.0, places=2,
            msg="credit_used should reflect the open invoice amount.")
        self.assertEqual(partner.credit_status, 'near_limit',
            "85% of credit limit should be 'near_limit'.")

        # Step 6 & 7 — push to exceeded
        self._post_invoice(partner, 2000.0)
        self._refresh_credit(partner)

        self.assertAlmostEqual(partner.credit_used, 10500.0, places=2,
            msg="credit_used should sum both open invoices.")
        self.assertEqual(partner.credit_status, 'exceeded',
            "Total invoices > credit limit should be 'exceeded'.")

    # ── test_integration_contract_lifecycle_full ──────────────────────────────

    def test_integration_contract_lifecycle_full(self):
        """
        Scenario: a contract is created, activated, then terminated via the
        wizard — exercising the full draft → active → terminated lifecycle
        on a real partner that also has an open invoice and credit status.

        Steps
        -----
        1.  Create a corporate partner with credit_limit 20,000.
        2.  Create a draft contract with 30% discount.
        3.  Assert initial state = 'draft'.
        4.  Cannot terminate a draft contract (guard check).
        5.  Activate the contract → state = 'active'.
        6.  Cannot activate an already-active contract (guard check).
        7.  Post an invoice to the partner and recompute credit.
        8.  Assert the partner's credit_status reflects the invoice.
        9.  Open the termination wizard and submit a reason.
        10. Assert state = 'terminated', metadata populated.
        11. Cannot terminate an already-terminated contract.
        12. Cron: create a separate active contract past its end date;
            run _cron_expire_contracts and assert it becomes 'expired'.
        """
        today = fields.Date.today()
        partner = self._make_corporate_partner(
            'Lifecycle Partner', credit_limit=20000.0
        )

        # Step 2-3
        contract = self._make_contract(
            partner, 'Lifecycle Contract', 'LC-INT-001', discount=30.0
        )
        self.assertEqual(contract.state, 'draft')
        self.assertAlmostEqual(contract.discount_pct, 30.0, places=2)

        # Step 4 — cannot terminate draft
        with self.assertRaises(UserError,
                msg="Terminating a draft contract must raise UserError."):
            contract.action_terminate()

        # Step 5 — activate
        contract.action_activate()
        self.assertEqual(contract.state, 'active')

        # Step 6 — cannot activate again
        with self.assertRaises(UserError,
                msg="Activating an active contract must raise UserError."):
            contract.action_activate()

        # Step 7-8 — invoice and credit status
        self._post_invoice(partner, 15000.0)
        self._refresh_credit(partner)
        self.assertAlmostEqual(partner.credit_used, 15000.0, places=2)
        # 15,000 / 20,000 = 75% → ok (below 80% threshold)
        self.assertEqual(partner.credit_status, 'ok',
            "75% utilisation should be 'ok'.")

        # Step 9-10 — terminate via wizard
        wizard = self.Wizard.create({
            'contract_id': contract.id,
            'reason': 'Partnership restructured — full lifecycle test.',
        })
        wizard.action_terminate()

        self.assertEqual(contract.state, 'terminated')
        self.assertEqual(
            contract.termination_reason,
            'Partnership restructured — full lifecycle test.',
        )
        self.assertEqual(contract.terminated_by, self.env.user)
        self.assertTrue(contract.terminated_at,
            "terminated_at must be set after termination.")

        # Step 11 — cannot terminate again
        with self.assertRaises(UserError,
                msg="Terminating an already-terminated contract must raise UserError."):
            contract.action_terminate()

        # Step 12 — cron expiry of a separate contract
        expired_contract = self.Contract.create({
            'name': 'Past Contract Lifecycle',
            'code': 'LC-PAST-001',
            'partner_id': partner.id,
            'start_date': today - timedelta(days=60),
            'end_date': today - timedelta(days=1),
            'state': 'active',
        })
        self.Contract._cron_expire_contracts()
        self.assertEqual(expired_contract.state, 'expired',
            "Contract with end_date yesterday must be expired by cron.")