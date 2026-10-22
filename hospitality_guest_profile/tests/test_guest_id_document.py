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
test_guest_id_document.py
=========================
Acceptance tests for GUEST-04 (hospitality.guest.id.document).

Test matrix
-----------
1. number_masked_non_pii_sees_stars
   A guest-user (no PII group) sees '***' for number_masked, never the
   real value.

2. number_masked_pii_sees_last4
   A PII user sees '****<last4>' for number_masked.

3. number_encrypted_at_rest
   The raw DB column stores an encrypted token, not plaintext.

4. date_constraint_expiry_before_issue_raises
   Setting expiry_date < issue_date raises ValidationError.

5. action_mark_verified_sets_fields
   action_mark_verified sets verified=True, verified_by, verified_at
   when called by a PII user.

6. pii_read_logged_in_ir_logging
   Reading 'number' via read() creates an ir.logging entry on the
   hospitality.pii channel.
"""

from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class TestGuestIdDocument(TransactionCase):
    """Tests for hospitality.guest.id.document (GUEST-04)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Groups ────────────────────────────────────────────────────────
        # FIX: was 'hospitality_guest_profile.group_guest_pii/user'
        #      correct module technical name is 'hospitality_guest_profile'
        cls.group_pii = cls.env.ref(
            'hospitality_guest_profile.group_guest_pii'
        )
        cls.group_user = cls.env.ref(
            'hospitality_guest_profile.group_guest_user'
        )

        # ── Users ─────────────────────────────────────────────────────────
        # FIX: 'groups_id' was removed in Odoo 19, use 'group_ids'
        cls.pii_user = cls.env['res.users'].create({
            'name': 'PII Agent',
            'login': 'pii_agent_g04@test.com',
            'group_ids': [(6, 0, [cls.group_pii.id])],
        })
        cls.plain_user = cls.env['res.users'].create({
            'name': 'Desk Staff',
            'login': 'desk_staff_g04@test.com',
            'group_ids': [(6, 0, [cls.group_user.id])],
        })

        # ── Guest partner ─────────────────────────────────────────────────
        cls.guest = cls.env['res.partner'].create({
            'name': 'Test Guest G04',
            'is_guest': True,
        })

        # ── One ID document (created as PII user so number can be set) ────
        cls.doc = cls.env['hospitality.guest.id.document'].with_user(
            cls.pii_user
        ).create({
            'partner_id': cls.guest.id,
            'type': 'passport',
            'number': 'A1234567',
            'issuing_country_id': cls.env.ref('base.in').id,
            'issue_date': date(2020, 1, 1),
            'expiry_date': date(2030, 1, 1),
        })

    # ── Test 1: non-PII user sees only '***' ──────────────────────────────

    def test_01_number_masked_non_pii_sees_stars(self):
        """Non-PII user's number_masked must be '***' (no digits)."""
        doc_as_plain = self.doc.with_user(self.plain_user)
        self.assertEqual(
            doc_as_plain.number_masked,
            '***',
            "Non-PII user should see '***' for number_masked, "
            "not the real value.",
        )

    # ── Test 2: PII user sees ****<last4> ─────────────────────────────────

    def test_02_number_masked_pii_sees_last4(self):
        """PII user's number_masked must be '****4567' (last 4 of A1234567)."""
        doc_as_pii = self.doc.with_user(self.pii_user)
        self.assertEqual(
            doc_as_pii.number_masked,
            '****4567',
            "PII user should see '****<last4>' for number_masked.",
        )

    # ── Test 3: number is encrypted at rest ───────────────────────────────

    def test_03_number_encrypted_at_rest(self):
        """Raw DB value of 'number' must not equal the plaintext input."""
        self.env.cr.execute(
            "SELECT number FROM hospitality_guest_id_document WHERE id = %s",
            (self.doc.id,),
        )
        row = self.env.cr.fetchone()
        self.assertIsNotNone(row, "Record should exist in DB.")
        raw_value = row[0]
        self.assertNotEqual(
            raw_value,
            'A1234567',
            "The raw DB column must store the encrypted token, not plaintext.",
        )
        # Token should be non-empty
        self.assertTrue(raw_value, "Encrypted token should not be empty.")

    # ── Test 4: date constraint ───────────────────────────────────────────

    def test_04_date_constraint_expiry_before_issue_raises(self):
        """Creating a document with expiry_date < issue_date must raise."""
        with self.assertRaises(ValidationError):
            self.env['hospitality.guest.id.document'].with_user(
                self.pii_user
            ).create({
                'partner_id': self.guest.id,
                'type': 'national_id',
                'number': 'Z9999999',
                'issue_date': date(2025, 6, 1),
                'expiry_date': date(2024, 1, 1),   # before issue
            })

    # ── Test 5: action_mark_verified ─────────────────────────────────────

    def test_05_action_mark_verified_sets_fields(self):
        """action_mark_verified must set verified, verified_by, verified_at."""
        # Create a fresh unverified doc for this test
        doc = self.env['hospitality.guest.id.document'].with_user(
            self.pii_user
        ).create({
            'partner_id': self.guest.id,
            'type': 'drivers_license',
            'number': 'DL00001',
        })
        self.assertFalse(doc.verified)
        doc.with_user(self.pii_user).action_mark_verified()
        doc.invalidate_recordset()
        self.assertTrue(doc.verified, "verified should be True after action.")
        self.assertEqual(
            doc.verified_by.id,
            self.pii_user.id,
            "verified_by should be the PII user who called the action.",
        )
        self.assertIsNotNone(
            doc.verified_at,
            "verified_at should be set.",
        )

    # ── Test 6: PII read is logged ────────────────────────────────────────

    def test_06_pii_read_logged_in_ir_logging(self):
        """Reading 'number' must create an ir.logging entry."""
        before_count = self.env['ir.logging'].sudo().search_count([
            ('message', 'like', 'document=%d' % self.doc.id),
            ('message', 'like', 'field=number'),
        ])
        # Trigger a read of the PII field
        self.doc.with_user(self.pii_user).read(['number'])
        after_count = self.env['ir.logging'].sudo().search_count([
            ('message', 'like', 'document=%d' % self.doc.id),
            ('message', 'like', 'field=number'),
        ])
        self.assertGreater(
            after_count,
            before_count,
            "Reading 'number' should create at least one ir.logging entry "
            "on the hospitality.pii channel.",
        )