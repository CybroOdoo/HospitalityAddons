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
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install', 'hospitality')
class TestBase07Sequences(TransactionCase):
    """BASE-07 — Sequence auto-creation, cron, and demo data."""

    # ------------------------------------------------------------------
    # Test 1 — All 3 sequences auto-created on property create
    # ------------------------------------------------------------------
    def test_01_sequences_auto_created(self):
        """Creating a property without sequences creates all three."""
        prop = self.env['hospitality.property'].create({
            'name': 'Sequence Test Hotel',
            'code': 'SEQ01',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': self.env.company.currency_id.id,
        })
        self.assertTrue(
            prop.sequence_reservation_id,
            "Reservation sequence should be auto-created.",
        )
        self.assertTrue(
            prop.sequence_folio_id,
            "Folio sequence should be auto-created.",
        )
        self.assertTrue(
            prop.sequence_invoice_id,
            "Invoice sequence should be auto-created.",
        )

    # ------------------------------------------------------------------
    # Test 2 — Sequence prefixes follow the spec format
    # ------------------------------------------------------------------
    def test_02_sequence_prefixes(self):
        """Auto-created sequences have correct prefix format."""
        prop = self.env['hospitality.property'].create({
            'name': 'Prefix Test Hotel',
            'code': 'PFX01',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': self.env.company.currency_id.id,
        })
        self.assertIn(
            'RES/PFX01/',
            prop.sequence_reservation_id.prefix,
            "Reservation prefix must contain RES/<code>/.",
        )
        self.assertIn(
            'FOL/PFX01/',
            prop.sequence_folio_id.prefix,
            "Folio prefix must contain FOL/<code>/.",
        )
        self.assertIn(
            'INV/PFX01/',
            prop.sequence_invoice_id.prefix,
            "Invoice prefix must contain INV/<code>/.",
        )

    # ------------------------------------------------------------------
    # Test 3 — Explicit sequences are not overwritten
    # ------------------------------------------------------------------
    def test_03_explicit_sequence_not_overwritten(self):
        """If caller supplies sequence_reservation_id, it must be kept."""
        custom_seq = self.env['ir.sequence'].create({
            'name': 'Custom Reservation',
            'code': 'custom.res.test',
            'prefix': 'CUSTOM/',
            'padding': 5,
        })
        prop = self.env['hospitality.property'].create({
            'name': 'Custom Seq Hotel',
            'code': 'CST01',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': self.env.company.currency_id.id,
            'sequence_reservation_id': custom_seq.id,
        })
        self.assertEqual(
            prop.sequence_reservation_id.id,
            custom_seq.id,
            "Explicitly provided sequence must not be overwritten.",
        )

    # ------------------------------------------------------------------
    # Test 4 — Cron does not fire for up-to-date properties
    # ------------------------------------------------------------------
    def test_04_cron_no_warning_for_current(self):
        """Cron must not post messages for properties with today's date."""
        prop = self.env['hospitality.property'].create({
            'name': 'Current Date Hotel',
            'code': 'CUR01',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': self.env.company.currency_id.id,
        })
        # Force business_date to today as admin
        prop.with_user(self.env.ref('base.user_admin')).write({
            'business_date': fields.Date.today(),
        })
        msg_count_before = len(prop.message_ids)
        self.env['hospitality.property']._cron_business_date_safety()
        msg_count_after = len(prop.message_ids)
        self.assertEqual(
            msg_count_before,
            msg_count_after,
            "No chatter message should be posted for a current property.",
        )

    # ------------------------------------------------------------------
    # Test 5 — Cron posts warning for lagging property
    # ------------------------------------------------------------------
    def test_05_cron_warns_lagging_property(self):
        """Cron must post a chatter message when business_date is stale."""
        prop = self.env['hospitality.property'].create({
            'name': 'Lagging Date Hotel',
            'code': 'LAG01',
            'property_type': 'hotel',
            'timezone': 'UTC',
            'currency_id': self.env.company.currency_id.id,
        })
        # Set business_date 3 days in the past as admin
        stale_date = fields.Date.today() - timedelta(days=3)
        prop.with_user(self.env.ref('base.user_admin')).write({
            'business_date': stale_date,
        })
        msg_count_before = len(prop.message_ids)
        self.env['hospitality.property']._cron_business_date_safety()
        msg_count_after = len(prop.message_ids)
        self.assertGreater(
            msg_count_after,
            msg_count_before,
            "A chatter warning must be posted for a lagging property.",
        )