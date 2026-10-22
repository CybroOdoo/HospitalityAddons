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
from unittest.mock import patch
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


class TestHospitalityRateAudit(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.property = cls.env['hospitality.property'].create({
            'name': 'Test Hotel',
            'code': 'THTL',
        })
        cls.rate_code = cls.env['hospitality.rate.code'].create(
            {'name': 'BAR', 'code': 'BAR', 'property_id': cls.property.id})
        cls.space_type = cls.env['hospitality.space.type'].create(
            {'name': 'Deluxe Room', 'code': 'DLX', 'property_id': cls.property.id})

        cls.plan = cls.env['hospitality.rate.plan'].create({
            'rate_code_id': cls.rate_code.id,
            'space_type_id': cls.space_type.id,
            'date_from': '2026-01-01',
            'date_to': '2026-12-31',
            'price_double': 100.0,
            'occupancy_pricing': 'flat',
        })

        # Set up users
        cls.user_rate_admin = cls.env['res.users'].create({
            'name': 'Rate Admin',
            'login': 'rate_admin',
            'group_ids': [
                (6, 0, [cls.env.ref('hospitality_rate.group_rate_admin').id, cls.env.ref('base.group_user').id])]
        })

        cls.user_rate_user = cls.env['res.users'].create({
            'name': 'Rate User',
            'login': 'rate_user',
            'group_ids': [
                (6, 0, [cls.env.ref('hospitality_rate.group_rate_user').id, cls.env.ref('base.group_user').id])]
        })

    def test_audit_row_created_on_plan_write(self):
        """Standard write creates an audit log"""
        self.plan.with_user(self.user_rate_admin).write({'price_double': 150.0})

        audit = self.env['hospitality.rate.audit'].search([('record_id', '=', self.plan.id)], limit=1)
        self.assertTrue(audit, "Audit row should be created.")
        self.assertEqual(audit.model, 'hospitality.rate.plan')
        self.assertEqual(audit.changed_by, self.user_rate_admin)

    def test_audit_locked_blocks_non_admin(self):
        """A normal user cannot edit a locked plan."""
        with patch('odoo.addons.hospitality_rate.models.hospitality_rate_plan.HospitalityRatePlan._is_audit_locked',
                   return_value=True):
            with self.assertRaises(AccessError):
                self.plan.with_user(self.user_rate_user).write({'price_double': 200.0})

    def test_audit_locked_requires_reason(self):
        """An admin can edit a locked plan ONLY IF they provide an audit_reason."""
        with patch('odoo.addons.hospitality_rate.models.hospitality_rate_plan.HospitalityRatePlan._is_audit_locked',
                   return_value=True):
            # Admin without reason -> FAILS
            with self.assertRaises(UserError):
                self.plan.with_user(self.user_rate_admin).write({'price_double': 250.0})

            # Admin with reason -> SUCCEEDS
            self.plan.with_user(self.user_rate_admin).write({
                'price_double': 250.0,
                'audit_reason': 'Manager override approved.'
            })

            audit = self.env['hospitality.rate.audit'].search([('record_id', '=', self.plan.id)], order='id desc',
                                                              limit=1)
            self.assertEqual(audit.reason, 'Manager override approved.')