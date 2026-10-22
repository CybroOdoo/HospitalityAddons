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

from dateutil.relativedelta import relativedelta

from odoo.fields import Datetime
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHospitalityPpm(TransactionCase):
    """MAINT-03: asset register + PPM templates + cron."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'MAINT-03 Test Property',
            'code': 'MT03',
        })
        cls.space_type = cls.env['hospitality.space.type'].create({
            'name': 'MAINT-03 Test Room Type',
            'code': 'MT03STD',
            'property_id': cls.property.id,
        })
        cls.space = cls.env['hospitality.space'].create({
            'name': 'MAINT-03 Test Room 201',
            'code': 'MT201',
            'property_id': cls.property.id,
            'space_type_id': cls.space_type.id,
        })

    def _create_asset(self, **extra):
        vals = {
            'name': 'MAINT-03 Test Asset',
            'code': 'AST-001',
            'property_id': self.property.id,
            'space_id': self.space.id,
            'category': 'equipment',
        }
        vals.update(extra)
        return self.env['hospitality.asset'].create(vals)

    def test_asset_parent_child(self):
        parent = self._create_asset(name='HVAC Unit', code='AST-P1')
        child = self._create_asset(
            name='HVAC Compressor', code='AST-C1',
            parent_asset_id=parent.id)

        self.assertIn(child, parent.child_asset_ids)
        self.assertEqual(child.parent_asset_id, parent)

    def test_ppm_cron_creates_wo_on_due_date(self):
        asset = self._create_asset()
        template = self.env['hospitality.ppm.template'].create({
            'name': 'MAINT-03 Test PPM',
            'asset_id': asset.id,
            'frequency': 'monthly',
            'task_template_text': 'Quarterly HVAC filter check',
        })
        # Never run yet, so next_run_at defaults to "now" (due immediately).
        # A small buffer avoids flaking on microsecond precision:
        # create_date keeps microseconds, fields.Datetime.now() truncates
        # to whole seconds, so a same-instant comparison can land either
        # side of "now" by a fraction of a second.
        self.assertLessEqual(
            template.next_run_at, Datetime.now() + timedelta(seconds=2))

        orders_before = self.env['hospitality.work.order'].search_count(
            [('asset_id', '=', asset.id)])

        self.env['hospitality.ppm.template']._cron_run_ppm_templates()

        orders_after = self.env['hospitality.work.order'].search_count(
            [('asset_id', '=', asset.id)])
        self.assertEqual(orders_after, orders_before + 1)

        created = self.env['hospitality.work.order'].search(
            [('asset_id', '=', asset.id)], limit=1, order='id desc')
        self.assertEqual(created.source, 'ppm')
        self.assertEqual(created.description, template.task_template_text)
        self.assertEqual(created.property_id, asset.property_id)
        self.assertEqual(created.space_id, asset.space_id)

        self.assertTrue(template.last_run_at)
        expected_next = template.last_run_at + relativedelta(months=1)
        self.assertEqual(template.next_run_at, expected_next)

    def test_ppm_cron_skips_not_yet_due_templates(self):
        asset = self._create_asset(code='AST-002')
        template = self.env['hospitality.ppm.template'].create({
            'name': 'MAINT-03 Future PPM',
            'asset_id': asset.id,
            'frequency': 'weekly',
        })
        # Simulate a recent run so it isn't due again yet.
        template.last_run_at = Datetime.now()
        self.assertGreater(template.next_run_at, Datetime.now())

        orders_before = self.env['hospitality.work.order'].search_count(
            [('asset_id', '=', asset.id)])
        self.env['hospitality.ppm.template']._cron_run_ppm_templates()
        orders_after = self.env['hospitality.work.order'].search_count(
            [('asset_id', '=', asset.id)])
        self.assertEqual(orders_before, orders_after)

    def test_next_run_computed_correctly(self):
        base = Datetime.now() - timedelta(days=1)
        cases = [
            ('daily', relativedelta(days=1)),
            ('weekly', relativedelta(weeks=1)),
            ('monthly', relativedelta(months=1)),
            ('quarterly', relativedelta(months=3)),
            ('semi_annual', relativedelta(months=6)),
            ('annual', relativedelta(years=1)),
        ]
        for frequency, delta in cases:
            template = self.env['hospitality.ppm.template'].create({
                'name': 'MAINT-03 Frequency Test %s' % frequency,
                'asset_category': 'equipment',
                'frequency': frequency,
                'last_run_at': base,
            })
            self.assertEqual(
                template.next_run_at, base + delta,
                "next_run_at mismatch for frequency=%s" % frequency)

        custom = self.env['hospitality.ppm.template'].create({
            'name': 'MAINT-03 Frequency Test custom_days',
            'asset_category': 'equipment',
            'frequency': 'custom_days',
            'custom_days': 45,
            'last_run_at': base,
        })
        self.assertEqual(custom.next_run_at, base + relativedelta(days=45))