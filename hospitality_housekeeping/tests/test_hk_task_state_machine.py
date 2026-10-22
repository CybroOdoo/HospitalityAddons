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
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.fields import Date


@tagged('post_install', '-at_install')
class TestHkTaskStateMachine(TransactionCase):
    """Covers the hospitality.housekeeping.task state machine and the
    attendant/supervisor record-rule scoping.

    NOTE: property/space fixtures below use only a minimal field set
    (name/code). If hospitality.property or hospitality.space carry
    other required fields in this database, adjust setUpClass to
    match before running.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HkTask = cls.env['hospitality.housekeeping.task']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Test Property',
                'code': 'HKTEST',
            })

        cls.space_type = cls.env['hospitality.space.type'].search(
            [], limit=1)
        if not cls.space_type:
            cls.space_type = cls.env['hospitality.space.type'].create({
                'name': 'HK Test Type',
            })

        cls.space = cls.env['hospitality.space'].search(
            [('property_id', '=', cls.property.id)], limit=1)
        if not cls.space:
            cls.space = cls.env['hospitality.space'].create({
                'name': 'HK Test Space 101',
                'code': 'HKTEST101',
                'property_id': cls.property.id,
                'space_type_id': cls.space_type.id,
            })

        cls.group_attendant = cls.env.ref(
            'hospitality_housekeeping.group_hk_attendant')
        cls.group_supervisor = cls.env.ref(
            'hospitality_housekeeping.group_hk_supervisor')

        cls.attendant_user = cls.env['res.users'].create({
            'name': 'HK Attendant',
            'login': 'hk_attendant_sm_test',
            'group_ids': [(4, cls.group_attendant.id)],
        })
        cls.other_attendant_user = cls.env['res.users'].create({
            'name': 'HK Other Attendant',
            'login': 'hk_other_attendant_sm_test',
            'group_ids': [(4, cls.group_attendant.id)],
        })

    def _create_task(self, task_type='departure', business_date=None):
        return self.HkTask.create({
            'property_id': self.property.id,
            'space_id': self.space.id,
            'business_date': business_date or Date.today(),
            'task_type': task_type,
        })

    def test_state_machine_transitions(self):
        """pending -> in_progress -> done -> inspected happy path,
        plus the dnd side path, all move state and stamp timestamps
        as expected."""
        task = self._create_task(task_type='departure')
        self.assertEqual(task.state, 'pending')

        task.action_assign(attendant_user_id=self.attendant_user.id)
        self.assertEqual(task.state, 'in_progress')
        self.assertEqual(task.attendant_user_id, self.attendant_user)
        self.assertTrue(task.started_at)

        task.action_set_dnd()
        self.assertEqual(task.state, 'dnd')

        task.action_clear_dnd()
        self.assertEqual(task.state, 'pending')

        task.action_assign(attendant_user_id=self.attendant_user.id)
        task.action_finish()
        self.assertEqual(task.state, 'done')
        self.assertTrue(task.finished_at)

        task.action_inspect()
        self.assertEqual(task.state, 'inspected')
        self.assertTrue(task.inspected_at)

    def test_invalid_transitions_raise(self):
        """Calling an action from a state it doesn't apply to raises
        a UserError rather than silently mutating the record."""
        task = self._create_task(task_type='stayover')

        # Can't finish a task that hasn't been assigned yet.
        with self.assertRaises(UserError):
            task.action_finish()

        # Can't inspect a task that isn't done yet.
        with self.assertRaises(UserError):
            task.action_inspect()

        task.action_assign(attendant_user_id=self.attendant_user.id)

        # Can't assign a task that is already in progress.
        with self.assertRaises(UserError):
            task.action_assign(attendant_user_id=self.other_attendant_user.id)

        # Can't clear dnd on a task that isn't in dnd.
        with self.assertRaises(UserError):
            task.action_clear_dnd()

    def test_inspection_updates_space_status_correctly(self):
        """Inspecting a departure task sets the space to vacant_clean;
        inspecting a stayover task sets it to occupied_clean."""
        departure_task = self._create_task(task_type='departure')
        departure_task.action_assign(attendant_user_id=self.attendant_user.id)
        departure_task.action_finish()
        departure_task.action_inspect()
        self.assertEqual(departure_task.space_id.status, 'vacant_clean')

        stayover_space = self.env['hospitality.space'].create({
            'name': 'HK Test Space 102',
            'code': 'HKTEST102',
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
        })
        stayover_task = self.HkTask.create({
            'property_id': self.property.id,
            'space_id': stayover_space.id,
            'business_date': Date.today(),
            'task_type': 'stayover',
        })
        stayover_task.action_assign(attendant_user_id=self.attendant_user.id)
        stayover_task.action_finish()
        stayover_task.action_inspect()
        self.assertEqual(stayover_task.space_id.status, 'occupied_clean')

    def test_attendant_sees_only_own_tasks(self):
        """The attendant record rule scopes the list to tasks
        assigned to that attendant's user, not tasks assigned to
        someone else."""
        own_task = self._create_task(task_type='turndown')
        own_task.action_assign(attendant_user_id=self.attendant_user.id)

        other_space = self.env['hospitality.space'].create({
            'name': 'HK Test Space 103',
            'code': 'HKTEST103',
            'property_id': self.property.id,
            'space_type_id': self.space_type.id,
        })
        other_task = self.HkTask.create({
            'property_id': self.property.id,
            'space_id': other_space.id,
            'business_date': Date.today(),
            'task_type': 'turndown',
        })
        other_task.action_assign(attendant_user_id=self.other_attendant_user.id)

        visible_tasks = self.HkTask.with_user(self.attendant_user).search([])
        self.assertIn(own_task, visible_tasks)
        self.assertNotIn(other_task, visible_tasks)