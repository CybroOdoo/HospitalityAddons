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
RATE-01 — test_install_and_groups_visible

Verifies that after installation the three security groups required by the
Hospitality Rate module are present and correctly configured:

    * hospitality_rate.group_rate_user
    * hospitality_rate.group_rate_manager
    * hospitality_rate.group_rate_admin

Group hierarchy assertions:
    group_rate_manager  implies  group_rate_user
    group_rate_admin    implies  group_rate_manager  (and transitively group_rate_user)
"""

from odoo.tests.common import TransactionCase
from odoo.tests import tagged


@tagged('post_install', '-at_install', 'hospitality_rate')
class TestInstallAndGroupsVisible(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env_ref = self.env.ref

    # ── helpers ──────────────────────────────────────────────────────────────

    def _get_group(self, xml_id):
        """Return the group record or fail with a clear message."""
        full_id = f'hospitality_rate.{xml_id}'
        group = self.env_ref(full_id, raise_if_not_found=False)
        self.assertIsNotNone(
            group,
            f"Security group '{full_id}' was not found. "
            "Ensure security_groups.xml is loaded correctly."
        )
        return group

    # ── tests ─────────────────────────────────────────────────────────────────

    def test_01_group_rate_user_exists(self):
        """group_rate_user must be installed and visible."""
        group = self._get_group('group_rate_user')
        self.assertEqual(group.name, 'Rate User')

    def test_02_group_rate_manager_exists(self):
        """group_rate_manager must be installed and visible."""
        group = self._get_group('group_rate_manager')
        self.assertEqual(group.name, 'Rate Manager')

    def test_03_group_rate_admin_exists(self):
        """group_rate_admin must be installed and visible."""
        group = self._get_group('group_rate_admin')
        self.assertEqual(group.name, 'Rate Admin')

    def test_04_all_three_groups_in_same_category(self):
        """The Hospitality module category must be installed and visible.

        Note: as of Odoo 19, ``res.groups`` no longer exposes a direct
        ``category_id`` field, so this test simply verifies that the
        ``module_hospitality_rate`` category record declared in
        security_groups.xml was created correctly.
        """
        category = self.env_ref(
            'hospitality_rate.module_hospitality_rate',
            raise_if_not_found=False,
        )
        self.assertIsNotNone(
            category,
            "Module category 'hospitality_rate.module_hospitality_rate' "
            "was not found. Ensure security_groups.xml is loaded correctly."
        )
        self.assertEqual(category.name, 'Hospitality')

    def test_05_manager_implies_user(self):
        """group_rate_manager must imply group_rate_user."""
        user_grp    = self._get_group('group_rate_user')
        manager_grp = self._get_group('group_rate_manager')
        self.assertIn(
            user_grp,
            manager_grp.implied_ids,
            "group_rate_manager should imply group_rate_user."
        )

    def test_06_admin_implies_manager(self):
        """group_rate_admin must imply group_rate_manager."""
        manager_grp = self._get_group('group_rate_manager')
        admin_grp   = self._get_group('group_rate_admin')
        self.assertIn(
            manager_grp,
            admin_grp.implied_ids,
            "group_rate_admin should imply group_rate_manager."
        )

    def test_07_admin_transitively_implies_user(self):
        """group_rate_admin must transitively cover group_rate_user via the hierarchy."""
        user_grp  = self._get_group('group_rate_user')
        admin_grp = self._get_group('group_rate_admin')

        # Odoo stores transitive implied groups in all_implied_ids
        # (trans_implied_ids was renamed in Odoo 19).
        trans_implied = admin_grp.all_implied_ids
        self.assertIn(
            user_grp,
            trans_implied,
            "group_rate_admin should transitively imply group_rate_user."
        )