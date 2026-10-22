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
from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHkAttendantSheetRenders(TransactionCase):
    """HK-04: report_hk_attendant_sheet renders cleanly and groups
    tasks by attendant in floor -> space code route order.

    NOTE: property/space/floor fixtures use only a minimal field
    set. If hospitality.property, hospitality.building,
    hospitality.floor or hospitality.space carry other required
    fields in this database, adjust setUpClass to match.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HkTask = cls.env['hospitality.housekeeping.task']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Sheet Test Property',
                'code': 'HKSHEET',
            })

        cls.building = cls.env['hospitality.building'].create({
            'name': 'HK Sheet Test Building',
            'code': 'HKB1',
            'property_id': cls.property.id,
        })
        cls.floor_1 = cls.env['hospitality.floor'].create({
            'name': 'Floor 1',
            'code': 'F1',
            'building_id': cls.building.id,
            'sequence': 1,
        })
        cls.floor_2 = cls.env['hospitality.floor'].create({
            'name': 'Floor 2',
            'code': 'F2',
            'building_id': cls.building.id,
            'sequence': 2,
        })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Sheet Test Type',
            })

        cls.space_201 = cls.env['hospitality.space'].create({
            'name': 'Room 201', 'code': 'HKSHEET201',
            'property_id': cls.property.id, 'floor_id': cls.floor_2.id,
            'space_type_id': cls.space_type.id,
        })
        cls.space_105 = cls.env['hospitality.space'].create({
            'name': 'Room 105', 'code': 'HKSHEET105',
            'property_id': cls.property.id, 'floor_id': cls.floor_1.id,
            'space_type_id': cls.space_type.id,
        })
        cls.space_102 = cls.env['hospitality.space'].create({
            'name': 'Room 102', 'code': 'HKSHEET102',
            'property_id': cls.property.id, 'floor_id': cls.floor_1.id,
            'space_type_id': cls.space_type.id,
        })

        cls.group_attendant = cls.env.ref(
            'hospitality_housekeeping.group_hk_attendant')
        cls.attendant_a = cls.env['res.users'].create({
            'name': 'Attendant A',
            'login': 'hk_sheet_attendant_a',
            'group_ids': [(4, cls.group_attendant.id)],
        })

    def _create_task(self, space, task_type='stayover', attendant_user=None):
        task = self.HkTask.create({
            'property_id': self.property.id,
            'space_id': space.id,
            'business_date': Date.today(),
            'task_type': task_type,
        })
        if attendant_user:
            task.attendant_user_id = attendant_user
        return task

    def test_tasks_grouped_and_sorted_by_route_order(self):
        """Tasks for one attendant come back as a single group,
        sorted floor -> space code, regardless of creation order."""
        task_201 = self._create_task(
            self.space_201, attendant_user=self.attendant_a)
        task_105 = self._create_task(
            self.space_105, attendant_user=self.attendant_a)
        task_102 = self._create_task(
            self.space_102, attendant_user=self.attendant_a)

        tasks = task_201 + task_105 + task_102
        groups = tasks._get_attendant_sheet_groups()

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['attendant_name'], 'Attendant A')
        self.assertEqual(
            groups[0]['tasks'].mapped('space_id.code'),
            ['HKSHEET102', 'HKSHEET105', 'HKSHEET201'])

    def test_unassigned_tasks_grouped_separately(self):
        """A task with no attendant set falls into its own
        'Unassigned' group rather than crashing the grouping."""
        assigned = self._create_task(
            self.space_105, attendant_user=self.attendant_a)
        unassigned = self._create_task(self.space_201)

        groups = (assigned + unassigned)._get_attendant_sheet_groups()
        names = [g['attendant_name'] for g in groups]

        self.assertIn('Attendant A', names)
        self.assertIn('Unassigned', names)

    def test_report_renders_without_error(self):
        """The QWeb PDF template renders to HTML without raising,
        and includes the attendant's name and each space code."""
        task_105 = self._create_task(
            self.space_105, attendant_user=self.attendant_a)
        task_102 = self._create_task(
            self.space_102, attendant_user=self.attendant_a)

        html, _report_type = self.env['ir.actions.report']._render_qweb_html(
            'hospitality_housekeeping.report_hk_attendant_sheet_document',
            (task_105 + task_102).ids)

        html = html.decode() if isinstance(html, bytes) else html
        self.assertIn('Attendant A', html)
        self.assertIn('102', html)
        self.assertIn('105', html)