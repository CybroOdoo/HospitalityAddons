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
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestContractStateMachine(TransactionCase):
    """COMP-05 acceptance tests — hospitality.contract state machine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Contract = cls.env['hospitality.contract']
        cls.Wizard = cls.env['hospitality.contract.terminate.wizard']

        cls.partner = cls.env['res.partner'].create({
            'name': 'Contract Test Partner',
            'is_corporate_account': True,
        })

        today = fields.Date.today()
        cls.contract = cls.Contract.create({
            'name': 'Test Contract',
            'code': 'TC-001',
            'partner_id': cls.partner.id,
            'start_date': today,
            'end_date': today + timedelta(days=365),
        })

    # ── helpers ───────────────────────────────────────────────────────────────

    def _make_contract(self, name, code, start_offset=0, end_offset=365, state=None):
        """Create a fresh contract; optionally force a state for guard tests."""
        today = fields.Date.today()
        vals = {
            'name': name,
            'code': code,
            'partner_id': self.partner.id,
            'start_date': today + timedelta(days=start_offset),
            'end_date': today + timedelta(days=end_offset),
        }
        contract = self.Contract.create(vals)
        if state:
            # Bypass the guard for setup purposes
            contract.write({'state': state})
        return contract

    # ── test_state_transitions_valid ──────────────────────────────────────────

    def test_state_transitions_valid(self):
        """
        Given a draft contract
        When action_activate is called
        Then state becomes active.

        Given an active contract
        When the termination wizard submits a reason
        Then state becomes terminated with termination metadata set.
        """
        contract = self._make_contract('Valid Transitions', 'VT-001')
        self.assertEqual(contract.state, 'draft')

        # draft → active
        contract.action_activate()
        self.assertEqual(contract.state, 'active')

        # active → terminated via wizard
        wizard = self.Wizard.create({
            'contract_id': contract.id,
            'reason': 'Test termination reason',
        })
        wizard.action_terminate()

        self.assertEqual(contract.state, 'terminated')
        self.assertEqual(contract.termination_reason, 'Test termination reason')
        self.assertEqual(contract.terminated_by, self.env.user)
        self.assertTrue(contract.terminated_at)

    # ── test_state_transitions_invalid_raise ─────────────────────────────────

    def test_state_transitions_invalid_raise(self):
        """
        Given a draft contract
        When action_terminate (via guard) is called directly
        Then UserError is raised.

        Given a terminated contract
        When action_activate is called
        Then UserError is raised.
        """
        # Cannot terminate a draft contract
        draft_contract = self._make_contract('Invalid Term Draft', 'ITD-001')
        with self.assertRaises(UserError,
                msg="Terminating a draft contract must raise UserError."):
            draft_contract.action_terminate()

        # Cannot activate a terminated contract
        term_contract = self._make_contract('Invalid Activate Term', 'IAT-001',
                                            state='terminated')
        with self.assertRaises(UserError,
                msg="Activating a terminated contract must raise UserError."):
            term_contract.action_activate()

        # Cannot activate an already-active contract
        active_contract = self._make_contract('Invalid Activate Active', 'IAA-001',
                                              state='active')
        with self.assertRaises(UserError,
                msg="Activating an already-active contract must raise UserError."):
            active_contract.action_activate()

        # Cannot activate an expired contract
        expired_contract = self._make_contract('Invalid Activate Expired', 'IAE-001',
                                               state='expired')
        with self.assertRaises(UserError,
                msg="Activating an expired contract must raise UserError."):
            expired_contract.action_activate()

    # ── test_cron_expires_past_end_date ───────────────────────────────────────

    def test_cron_expires_past_end_date(self):
        """
        Given an active contract whose end_date is yesterday
        When _cron_expire_contracts runs
        Then state becomes expired.

        Given an active contract whose end_date is today
        When _cron_expire_contracts runs
        Then state stays active (today is NOT past end_date).
        """
        today = fields.Date.today()
        yesterday = today - timedelta(days=1)

        # Contract already past its end date — must expire
        past_contract = self.Contract.create({
            'name': 'Past Contract',
            'code': 'PAST-001',
            'partner_id': self.partner.id,
            'start_date': today - timedelta(days=30),
            'end_date': yesterday,
            'state': 'active',
        })

        # Contract ending today — must stay active (end_date < today is False)
        today_contract = self.Contract.create({
            'name': 'Today Contract',
            'code': 'TODAY-001',
            'partner_id': self.partner.id,
            'start_date': today - timedelta(days=30),
            'end_date': today,
            'state': 'active',
        })

        self.Contract._cron_expire_contracts()

        self.assertEqual(past_contract.state, 'expired',
            "Contract with end_date < today must be expired by cron.")
        self.assertEqual(today_contract.state, 'active',
            "Contract with end_date == today must remain active.")

    # ── test_end_date_after_start_date ────────────────────────────────────────

    def test_end_date_after_start_date(self):
        """
        Given end_date < start_date
        When the contract is created/saved
        Then ValidationError is raised.
        """
        today = fields.Date.today()
        with self.assertRaises(ValidationError,
                msg="end_date before start_date must raise ValidationError."):
            self.Contract.create({
                'name': 'Bad Dates Contract',
                'code': 'BD-001',
                'partner_id': self.partner.id,
                'start_date': today + timedelta(days=10),
                'end_date': today + timedelta(days=5),
            })

    # ── test_terminate_requires_reason ────────────────────────────────────────

    def test_terminate_requires_reason(self):
        """
        Given an active contract
        When the termination wizard is submitted with a blank reason
        Then UserError is raised and the contract remains active.
        """
        contract = self._make_contract('Reason Required', 'RR-001', state='active')

        # Empty string reason
        wizard_empty = self.Wizard.create({
            'contract_id': contract.id,
            'reason': '   ',
        })
        with self.assertRaises(UserError,
                msg="Blank reason must raise UserError."):
            wizard_empty.action_terminate()

        # Contract must still be active
        self.assertEqual(contract.state, 'active',
            "Contract must remain active when termination wizard fails.")