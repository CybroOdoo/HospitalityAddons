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
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestFrontDeskCheckOutWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Guest FD03', 'email': 'fd03guest@example.com'})
        cls.corporate_partner = cls.env['res.partner'].create({
            'name': 'FD03 Corp Guest', 'email': 'corp@example.com'})
        if 'is_corporate' in cls.env['res.partner']._fields:
            cls.corporate_partner.write({'is_corporate': True})

        cls.template_reservation = cls.env['hospitality.reservation'].search([
            ('property_id', '!=', False),
            ('space_type_id', '!=', False),
            ('rate_code_id', '!=', False),
        ], limit=1)
        if not cls.template_reservation:
            raise Exception('No valid reservation found. Install demo data first.')

        cls.property = cls.template_reservation.property_id
        cls.space_type = cls.template_reservation.space_type_id
        cls.rate_code = cls.template_reservation.rate_code_id

        cls.space = cls.env['hospitality.space'].create({
            'name': '201-FD03', 'code': '201FD03',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
            'status': 'vacant_clean',
        })

        supervisor_group = cls.env.ref('hospitality_front_desk.group_front_desk_supervisor')
        agent_group = cls.env.ref('hospitality_front_desk.group_front_desk_agent')
        base_group = cls.env.ref('base.group_user')

        cls.supervisor_user = cls.env['res.users'].create({
            'name': 'FD03 Supervisor', 'login': 'fd03_supervisor',
            'group_ids': [(6, 0, [supervisor_group.id, base_group.id])],
        })
        cls.agent_user = cls.env['res.users'].create({
            'name': 'FD03 Agent', 'login': 'fd03_agent',
            'group_ids': [(6, 0, [agent_group.id, base_group.id])],
        })

        cls.reservation = cls._make_checked_in_reservation(cls, cls.partner)

    def _make_checked_in_reservation(self, partner):
        res = self.template_reservation.copy({
            'partner_id': partner.id,
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
            'rate_code_id': self.rate_code.id,
            'space_id': self.space.id,
            'state': 'draft',
        })
        self.env.cr.execute(
            "UPDATE hospitality_reservation SET state = 'checked_in' WHERE id = %s",
            (res.id,)
        )
        res.invalidate_recordset()
        return res

    def _make_wizard(self, reservation=None, **kwargs):
        res = reservation or self.reservation
        vals = {'reservation_id': res.id, 'settle_now': False}
        vals.update(kwargs)
        return self.env['hospitality.front.desk.check.out.wizard'].create(vals)

    @property
    def _WizardCls(self):
        return type(self.env['hospitality.front.desk.check.out.wizard'])

    def test_checkout_blocks_with_balance_without_settlement(self):
        wiz = self._make_wizard(settle_now=True, settlement_method='cash')
        with patch.object(self._WizardCls, '_get_balance', return_value=150.0), \
             patch.object(self._WizardCls, '_current_user_is_supervisor', return_value=False):
            with self.assertRaises(UserError):
                wiz.action_check_out()

    def test_checkout_transfer_to_ar(self):
        res = self._make_checked_in_reservation(self.corporate_partner)
        wiz = self._make_wizard(reservation=res, settle_now=True, settlement_method='transfer_ar')
        with patch.object(self._WizardCls, '_get_balance', return_value=200.0), \
             patch.object(self._WizardCls, '_partner_has_open_ar', return_value=True), \
             patch.object(type(res), 'action_check_out', return_value=None):
            result = wiz.action_check_out()
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')

    def test_checkout_emails_invoice(self):
        wiz = self._make_wizard(settle_now=False, email_invoice_to='guest@example.com')
        email_called = []
        def _fake_email(self_wiz):
            email_called.append(True)
        with patch.object(self._WizardCls, '_get_balance', return_value=0.0), \
             patch.object(self._WizardCls, '_email_invoice', _fake_email), \
             patch.object(type(self.reservation), 'action_check_out', return_value=None):
            wiz.action_check_out()
        self.assertTrue(email_called)

    def test_checkout_supervisor_can_force_with_balance(self):
        wiz = self._make_wizard(settle_now=True, settlement_method='cash')
        with patch.object(self._WizardCls, '_get_balance', return_value=300.0), \
             patch.object(self._WizardCls, '_current_user_is_supervisor', return_value=True), \
             patch.object(type(self.reservation), 'action_check_out', return_value=None):
            result = wiz.action_check_out()
        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')

    def test_late_fee_posted(self):
        wiz = self._make_wizard(settle_now=False, late_checkout_fee=50.0)
        posted = []
        def _fake_post(self_wiz):
            posted.append(self_wiz.late_checkout_fee)
        with patch.object(self._WizardCls, '_get_balance', return_value=0.0), \
             patch.object(self._WizardCls, '_post_late_checkout_fee', _fake_post), \
             patch.object(type(self.reservation), 'action_check_out', return_value=None):
            wiz.action_check_out()
        self.assertTrue(posted)
        self.assertAlmostEqual(posted[0], 50.0)
