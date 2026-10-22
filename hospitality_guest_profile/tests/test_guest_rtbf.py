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
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC License
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
"""
test_guest_rtbf.py  (GUEST-06)
================================
Acceptance tests for the Right-To-Be-Forgotten (RTBF) anonymisation feature.

Test matrix
-----------
1. test_non_admin_cannot_execute_rtbf
   A guest_user (non-admin) calling action_execute raises AccessError.

2. test_rtbf_anonymises_partner_fields
   After execute, name = "Anonymized #<id>"; all PII fields are blank.

3. test_rtbf_preserves_history_lines
   Stay history lines survive the anonymisation (accounting integrity).

4. test_rtbf_blanks_id_document_fields
   ID document rows are kept but number/scan_front/scan_back are cleared.

5. test_rtbf_requires_confirmation_checkbox
   Calling action_execute without ticking confirm_irreversible raises UserError.
"""

from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestGuestRtbf(TransactionCase):
    """Tests for GUEST-06 RTBF / anonymisation wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Admin user — has group_guest_pii
        cls.admin_user = cls.env.ref('base.user_admin')

        # Create a plain internal user with only group_guest_user.
        # FIX: 'groups_id' was removed in Odoo 19, use 'group_ids'
        cls.guest_user = cls.env['res.users'].create({
            'name': 'Test Guest User',
            'login': 'test_guest_user_rtbf@test.com',
        })

        guest_group = cls.env.ref(
            'hospitality_guest_profile.group_guest_user'
        )

        # FIX: was 'groups_id' — Odoo 19 renamed this field to 'group_ids'
        cls.guest_user.write({
            'group_ids': [(4, guest_group.id)]
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_guest(self, name='RTBF Test Guest'):
        return self.env['res.partner'].with_user(self.admin_user).create({
            'name': name,
            'is_guest': True,
            'email': 'guest@example.com',
            'phone': '+1234567890',
            'street': '123 Test St',
            'street2': 'Apt 4',
            'city': 'Testville',
            'zip': '99999',
            'vat': 'US123456789',
            'birth_date': date(1990, 1, 1),
            'marketing_consent_email': True,
            'marketing_consent_sms': True,
        })

    def _make_wizard(self, partner, user=None):
        user = user or self.admin_user

        return self.env['hospitality.guest.rtbf.wizard'].with_user(
            user
        ).create({
            'partner_id': partner.id,
            'confirm_irreversible': True,
        })

    # ==================================================================
    # Test 1 — non-admin cannot execute
    # ==================================================================
    def test_non_admin_cannot_execute_rtbf(self):
        """A user without group_guest_pii must get AccessError on action_execute."""
        guest = self._make_guest('Non-admin target')

        wizard = self.env['hospitality.guest.rtbf.wizard'].with_user(
            self.admin_user
        ).create({
            'partner_id': guest.id,
            'confirm_irreversible': True,
        })

        with self.assertRaises(AccessError):
            wizard.with_user(self.guest_user).action_execute()

    # ==================================================================
    # Test 2 — anonymisation correct (acceptance criterion)
    # ==================================================================
    def test_rtbf_anonymises_partner_fields(self):
        """After execute, PII fields are blank and name = 'Anonymized #<id>'."""
        guest = self._make_guest('John Doe')
        partner_id = guest.id

        wizard = self._make_wizard(guest)
        wizard.action_execute()

        guest.invalidate_recordset()

        self.assertEqual(guest.name, f'Anonymized #{partner_id}')
        self.assertFalse(guest.email,   'email should be blank')
        self.assertFalse(guest.phone,   'phone should be blank')
        self.assertFalse(guest.street,  'street should be blank')
        self.assertFalse(guest.street2, 'street2 should be blank')
        self.assertFalse(guest.city,    'city should be blank')
        self.assertFalse(guest.zip,     'zip should be blank')
        self.assertFalse(guest.vat,     'vat should be blank')
        self.assertFalse(guest.birth_date, 'birth_date should be blank')
        self.assertFalse(guest.marketing_consent_email)
        self.assertFalse(guest.marketing_consent_sms)
        self.assertTrue(guest.rtbf_anonymized_at, 'rtbf_anonymized_at must be set')

    # ==================================================================
    # Test 3 — history lines preserved (acceptance criterion)
    # ==================================================================
    def test_rtbf_preserves_history_lines(self):
        """Stay history lines must survive anonymisation."""
        guest = self._make_guest('History Preserved Guest')

        self.env['hospitality.guest.history.line'].create([
            {
                'partner_id': guest.id,
                'check_in': date(2024, 1, 1),
                'check_out': date(2024, 1, 3),
                'revenue': 200.0,
            },
            {
                'partner_id': guest.id,
                'check_in': date(2024, 6, 1),
                'check_out': date(2024, 6, 5),
                'revenue': 400.0,
            },
        ])

        wizard = self._make_wizard(guest)
        wizard.action_execute()

        guest.invalidate_recordset()
        self.assertEqual(
            guest.total_stays, 2,
            'History lines must be preserved after RTBF',
        )
        self.assertAlmostEqual(guest.total_revenue, 600.0, places=2)

    # ==================================================================
    # Test 4 — ID document fields blanked but rows kept
    # ==================================================================
    def test_rtbf_blanks_id_document_fields(self):
        """ID document rows survive but number/scans are cleared."""
        guest = self._make_guest('ID Doc Guest')

        # FIX: was 'document_type' — the actual field name is 'type'
        doc = self.env['hospitality.guest.id.document'].create({
            'partner_id': guest.id,
            'type': 'passport',
            'number': 'AB123456',
        })
        doc_id = doc.id

        wizard = self._make_wizard(guest)
        wizard.action_execute()

        doc_after = self.env['hospitality.guest.id.document'].browse(doc_id)
        self.assertTrue(doc_after.exists(), 'ID document row must be kept')
        self.assertFalse(doc_after.number, 'Document number must be blanked')

    # ==================================================================
    # Test 5 — confirmation checkbox required
    # ==================================================================
    def test_rtbf_requires_confirmation_checkbox(self):
        """action_execute without ticking confirm_irreversible raises UserError."""
        guest = self._make_guest('Checkbox Required Guest')

        wizard = self.env['hospitality.guest.rtbf.wizard'].with_user(
            self.admin_user
        ).create({
            'partner_id': guest.id,
            'confirm_irreversible': False,
        })

        with self.assertRaises(UserError):
            wizard.action_execute()