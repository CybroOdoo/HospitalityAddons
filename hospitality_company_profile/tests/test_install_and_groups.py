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


@tagged('post_install', '-at_install')
class TestInstallAndGroups(TransactionCase):
    """COMP-01 acceptance: three security groups must be present after install."""

    # XML-IDs for the three groups defined in security_groups.xml
    _GROUP_XMLIDS = [
        'hospitality_company_profile.group_corporate_user',
        'hospitality_company_profile.group_corporate_manager',
        'hospitality_company_profile.group_corporate_finance',
    ]

    def test_groups_exist(self):
        """All three corporate groups resolve to a res.groups record."""
        for xmlid in self._GROUP_XMLIDS:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertIsNotNone(
                group,
                msg=f"Security group '{xmlid}' not found — check security_groups.xml.",
            )
            self.assertIsInstance(
                group._name == 'res.groups', bool,
                msg=f"'{xmlid}' resolved but is not a res.groups record.",
            )

    def test_manager_implies_user(self):
        """Corporate Manager must inherit Corporate User."""
        manager = self.env.ref('hospitality_company_profile.group_corporate_manager')
        user_group = self.env.ref('hospitality_company_profile.group_corporate_user')
        self.assertIn(
            user_group,
            manager.implied_ids,
            msg="group_corporate_manager should imply group_corporate_user.",
        )

    def test_finance_implies_user(self):
        """Corporate Finance must inherit Corporate User."""
        finance = self.env.ref('hospitality_company_profile.group_corporate_finance')
        user_group = self.env.ref('hospitality_company_profile.group_corporate_user')
        self.assertIn(
            user_group,
            finance.implied_ids,
            msg="group_corporate_finance should imply group_corporate_user.",
        )