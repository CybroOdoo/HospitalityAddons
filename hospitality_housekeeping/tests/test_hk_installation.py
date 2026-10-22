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
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHkInstallation(TransactionCase):
    """Install-time sanity checks for hospitality_housekeeping:
    the module loads cleanly and the HK security groups are wired
    up with the expected implied hierarchy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_attendant = cls.env.ref(
            'hospitality_housekeeping.group_hk_attendant')
        cls.group_supervisor = cls.env.ref(
            'hospitality_housekeeping.group_hk_supervisor')
        cls.group_user = cls.env.ref('base.group_user')

    def test_module_installed(self):
        """The module itself is present and marked installed."""
        module = self.env['ir.module.module'].search(
            [('name', '=', 'hospitality_housekeeping')])
        self.assertTrue(module, "hospitality_housekeeping module not found")
        self.assertEqual(module.state, 'installed')

    def test_hk_groups_exist(self):
        """Both HK groups are created with the expected names."""
        self.assertEqual(
            self.group_attendant.name, 'Housekeeping / Attendant')
        self.assertEqual(
            self.group_supervisor.name, 'Housekeeping / Supervisor')

    def test_attendant_implies_base_user(self):
        """Attendants get base internal-user access."""
        self.assertIn(self.group_user, self.group_attendant.implied_ids)

    def test_supervisor_implies_attendant(self):
        """Supervisors inherit everything an attendant can do."""
        self.assertIn(
            self.group_attendant, self.group_supervisor.implied_ids)

    def test_supervisor_user_has_attendant_access(self):
        """A user placed only in the supervisor group is recognised
        as having attendant-level access too, through the implied
        hierarchy."""
        test_user = self.env['res.users'].create({
            'name': 'HK Supervisor Test User',
            'login': 'hk_supervisor_test_user',
            'group_ids': [(4, self.group_supervisor.id)],
        })
        self.assertTrue(
            test_user.has_group(
                'hospitality_housekeeping.group_hk_supervisor'))
        self.assertTrue(
            test_user.has_group(
                'hospitality_housekeeping.group_hk_attendant'))

    def test_attendant_only_user_lacks_supervisor_access(self):
        """A plain attendant should not be recognised as a supervisor."""
        test_user = self.env['res.users'].create({
            'name': 'HK Attendant Test User',
            'login': 'hk_attendant_test_user',
            'group_ids': [(4, self.group_attendant.id)],
        })
        self.assertTrue(
            test_user.has_group(
                'hospitality_housekeeping.group_hk_attendant'))
        self.assertFalse(
            test_user.has_group(
                'hospitality_housekeeping.group_hk_supervisor'))