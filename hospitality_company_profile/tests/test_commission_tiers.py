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
class TestCommissionTiers(TransactionCase):
    """COMP-03 acceptance tests — commission tier overlap and compute_commission."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env['res.partner']
        cls.Tier = cls.env['hospitality.commission.tier']

        # Base partner used across tests
        cls.partner = cls.Partner.create({
            'name': 'Test Corporate Partner',
            'is_corporate_account': True,
        })

    # ── helpers ───────────────────────────────────────────────────────────────

    def _add_tier(self, lower, upper, pct, basis='revenue'):
        return self.Tier.create({
            'partner_id': self.partner.id,
            'volume_basis': basis,
            'lower_volume': lower,
            'upper_volume': upper,
            'commission_pct': pct,
        })

    def _set_method(self, method, pct=0.0):
        self.partner.write({'commission_method': method, 'commission_pct': pct})

    # ── test_overlap_rejected ─────────────────────────────────────────────────

    def test_overlap_rejected(self):
        """Two tiers for the same partner+basis that overlap must raise."""
        partner2 = self.Partner.create({
            'name': 'Overlap Test Partner',
            'is_corporate_account': True,
        })
        self.Tier.create({
            'partner_id': partner2.id,
            'volume_basis': 'revenue',
            'lower_volume': 0,
            'upper_volume': 1000,
            'commission_pct': 5,
        })
        with self.assertRaises(ValidationError, msg=(
            "Overlapping tiers on the same partner+basis must raise ValidationError."
        )):
            self.Tier.create({
                'partner_id': partner2.id,
                'volume_basis': 'revenue',
                'lower_volume': 500,   # overlaps with 0–1000
                'upper_volume': 2000,
                'commission_pct': 8,
            })

    def test_non_overlapping_tiers_ok(self):
        """Adjacent non-overlapping tiers must save without error."""
        partner3 = self.Partner.create({
            'name': 'Non-Overlap Test Partner',
            'is_corporate_account': True,
        })
        self.Tier.create({
            'partner_id': partner3.id,
            'volume_basis': 'revenue',
            'lower_volume': 0,
            'upper_volume': 1000,
            'commission_pct': 5,
        })
        tier2 = self.Tier.create({
            'partner_id': partner3.id,
            'volume_basis': 'revenue',
            'lower_volume': 1000,
            'upper_volume': 5000,
            'commission_pct': 8,
        })
        self.assertTrue(tier2.id)

    # ── test_compute_pct_room ─────────────────────────────────────────────────

    def test_compute_pct_room(self):
        """pct_room → commission_pct% of room_revenue."""
        self._set_method('pct_room', pct=10.0)
        result = self.partner.compute_commission(
            room_revenue=500.0,
            total_revenue=700.0,
            room_nights=3,
        )
        self.assertAlmostEqual(result, 50.0, places=2,
            msg="10% of 500 room revenue should be 50.0")

    # ── test_compute_pct_total ────────────────────────────────────────────────

    def test_compute_pct_total(self):
        """pct_total → commission_pct% of total_revenue."""
        self._set_method('pct_total', pct=8.0)
        result = self.partner.compute_commission(
            room_revenue=500.0,
            total_revenue=800.0,
            room_nights=3,
        )
        self.assertAlmostEqual(result, 64.0, places=2,
            msg="8% of 800 total revenue should be 64.0")

    # ── test_compute_fixed_per_stay ───────────────────────────────────────────

    def test_compute_fixed_per_stay(self):
        """fixed_per_stay → commission_pct is the fixed amount, returned as-is."""
        self._set_method('fixed_per_stay', pct=75.0)
        result = self.partner.compute_commission(
            room_revenue=500.0,
            total_revenue=800.0,
            room_nights=3,
        )
        self.assertAlmostEqual(result, 75.0, places=2,
            msg="Fixed per stay should return 75.0 regardless of revenues.")

    # ── test_compute_tiered_by_volume_revenue ─────────────────────────────────

    def test_compute_tiered_by_volume_revenue(self):
        """tiered_by_volume / revenue basis — correct tier matched."""
        self._set_method('tiered_by_volume')
        # Clear existing tiers on this partner
        self.partner.commission_tier_ids.unlink()

        self._add_tier(lower=0,    upper=500,  pct=5,  basis='revenue')
        self._add_tier(lower=500,  upper=2000, pct=10, basis='revenue')
        self._add_tier(lower=2000, upper=0,    pct=15, basis='revenue')  # open-ended

        # total_revenue=800 → hits 500–2000 tier → 10% of 800 = 80
        result = self.partner.compute_commission(
            room_revenue=600.0,
            total_revenue=800.0,
            room_nights=4,
        )
        self.assertAlmostEqual(result, 80.0, places=2,
            msg="Revenue 800 should match 500-2000 tier at 10% → 80.0")

    # ── test_compute_tiered_by_volume_nights ──────────────────────────────────

    def test_compute_tiered_by_volume_nights(self):
        """tiered_by_volume / nights basis — correct tier matched."""
        self._set_method('tiered_by_volume')
        self.partner.commission_tier_ids.unlink()

        self._add_tier(lower=0,  upper=3,  pct=5,  basis='nights')
        self._add_tier(lower=3,  upper=7,  pct=10, basis='nights')
        self._add_tier(lower=7,  upper=0,  pct=15, basis='nights')  # open-ended

        # room_nights=5 → hits 3–7 tier → 10% of total_revenue 900 = 90
        result = self.partner.compute_commission(
            room_revenue=600.0,
            total_revenue=900.0,
            room_nights=5,
        )
        self.assertAlmostEqual(result, 90.0, places=2,
            msg="5 nights should match 3-7 tier at 10% → 90.0")

    def test_compute_tiered_no_matching_tier_returns_zero(self):
        """When no tier matches the volume value, return 0."""
        self._set_method('tiered_by_volume')
        self.partner.commission_tier_ids.unlink()

        self._add_tier(lower=0, upper=100, pct=5, basis='revenue')

        # total_revenue=5000 → no tier covers it
        result = self.partner.compute_commission(
            room_revenue=4000.0,
            total_revenue=5000.0,
            room_nights=10,
        )
        self.assertAlmostEqual(result, 0.0, places=2,
            msg="No matching tier should return 0.0")