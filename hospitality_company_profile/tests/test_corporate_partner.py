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
from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestCorporatePartner(TransactionCase):
    """COMP-02 acceptance tests for res.partner corporate/TA/OTA extension."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']

    # ── helper ────────────────────────────────────────────────────────────────

    def _make_partner(self, **kw):
        return self.Partner.create({'name': 'Test Partner', **kw})

    # ── test_cannot_be_guest_and_corporate ────────────────────────────────────

    def test_cannot_be_guest_and_corporate(self):
        """A partner with is_guest=True must not be flagged as corporate."""
        # Only run if is_guest field actually exists on res.partner
        # (added by hospitality_guest_profile); skip gracefully if absent.
        if 'is_guest' not in self.Partner._fields:
            self.skipTest('is_guest field not present — hospitality_guest_profile not installed')

        partner = self._make_partner(is_guest=True)
        with self.assertRaises(ValidationError, msg=(
            "Setting is_corporate_account=True on a guest partner should raise."
        )):
            partner.is_corporate_account = True
            partner._check_not_guest_and_corporate()

    def test_cannot_be_guest_and_ta(self):
        """A partner with is_guest=True must not be flagged as Travel Agent."""
        if 'is_guest' not in self.Partner._fields:
            self.skipTest('is_guest field not present — hospitality_guest_profile not installed')

        partner = self._make_partner(is_guest=True)
        with self.assertRaises(ValidationError):
            partner.is_travel_agent = True
            partner.iata_number = 'XX12345678'
            partner._check_not_guest_and_corporate()

    def test_cannot_be_guest_and_ota(self):
        """A partner with is_guest=True must not be flagged as OTA."""
        if 'is_guest' not in self.Partner._fields:
            self.skipTest('is_guest field not present — hospitality_guest_profile not installed')

        partner = self._make_partner(is_guest=True)
        with self.assertRaises(ValidationError):
            partner.is_ota = True
            partner._check_not_guest_and_corporate()

    # ── test_ta_requires_iata ─────────────────────────────────────────────────

    def test_ta_requires_iata(self):
        """Creating a Travel Agent without an IATA number must raise."""
        with self.assertRaises(ValidationError, msg=(
            "Travel Agent without iata_number should raise ValidationError."
        )):
            self._make_partner(is_travel_agent=True, iata_number=False)

    def test_ta_with_iata_saves_ok(self):
        """Creating a Travel Agent with a valid IATA number must succeed."""
        partner = self._make_partner(
            is_travel_agent=True,
            iata_number='IATA12345678',
        )
        self.assertTrue(partner.is_travel_agent)
        self.assertEqual(partner.iata_number, 'IATA12345678')

    def test_ta_with_whitespace_iata_raises(self):
        """An IATA number of only whitespace must also raise."""
        with self.assertRaises(ValidationError):
            self._make_partner(is_travel_agent=True, iata_number='   ')

    # ── test_corp_tab_visible_when_corporate ──────────────────────────────────

    def test_corp_tab_visible_when_corporate(self):
        """
        The view XML marks the tab invisible when none of the three flags
        is True. Verify that the computed helper is_any_corporate reflects
        that logic correctly (the actual DOM visibility is handled by the
        client; we test the server-side signal field here).
        """
        partner_plain = self._make_partner()
        self.assertFalse(
            partner_plain.is_any_corporate,
            msg="Tab signal should be False when no corporate flag is set.",
        )

        partner_corp = self._make_partner(is_corporate_account=True)
        self.assertTrue(
            partner_corp.is_any_corporate,
            msg="Tab signal should be True when is_corporate_account=True.",
        )

        partner_ta = self._make_partner(
            is_travel_agent=True,
            iata_number='IATA00000001',
        )
        self.assertTrue(
            partner_ta.is_any_corporate,
            msg="Tab signal should be True when is_travel_agent=True.",
        )

        partner_ota = self._make_partner(is_ota=True)
        self.assertTrue(
            partner_ota.is_any_corporate,
            msg="Tab signal should be True when is_ota=True.",
        )