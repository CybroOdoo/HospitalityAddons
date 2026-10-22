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
# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNightAuditInstall(TransactionCase):
    """NA-01: install sanity + security group checks."""

    def test_module_installed(self):
        module = self.env['ir.module.module'].search(
            [('name', '=', 'hospitality_night_audit')]
        )
        self.assertTrue(module, "hospitality_night_audit should be a registered module")
        self.assertEqual(module.state, 'installed')

    def test_group_night_auditor_exists(self):
        group = self.env.ref('hospitality_night_audit.group_night_auditor')
        self.assertTrue(group.exists())
        self.assertEqual(group.name, 'Night Auditor')

    def test_group_no_privilege(self):
        # Uncategorized on purpose so it renders under "Extra Rights"
        # instead of its own single-group toggle section.
        group = self.env.ref('hospitality_night_audit.group_night_auditor')
        self.assertFalse(group.privilege_id)