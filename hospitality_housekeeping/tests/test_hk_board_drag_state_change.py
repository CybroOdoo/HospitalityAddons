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
from odoo.fields import Date
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestHkBoardDragStateChange(TransactionCase):
    """HK-04: dragging a card between kanban columns arrives as a
    plain write({'state': ...}); the model's write() override must
    route that through the matching action_* method (with its
    validation and side effects) rather than writing state directly.

    NOTE: property/space fixtures use only a minimal field set. If
    hospitality.property or hospitality.space carry other required
    fields in this database, adjust setUpClass to match.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HkTask = cls.env['hospitality.housekeeping.task']

        cls.property = cls.env['hospitality.property'].search([], limit=1)
        if not cls.property:
            cls.property = cls.env['hospitality.property'].create({
                'name': 'HK Board Test Property',
                'code': 'HKBOARD',
            })

        cls.space = cls.env['hospitality.space'].search(
            [('property_id', '=', cls.property.id)], limit=1)
        if not cls.space:
            cls.space = cls.env['hospitality.space'].create({
                'name': 'HK Board Test Space',
                'property_id': cls.property.id,
            })

        cls.group_attendant = cls.env.ref(
            'hospitality_housekeeping.group_hk_attendant')
        cls.attendant_user = cls.env['res.users'].create({
            'name': 'HK Board Drag Attendant',
            'login': 'hk_board_drag_attendant',
            'group_ids': [(4, cls.group_attendant.id)],
        })

    def _create_task(self, task_type='departure'):
        return self.HkTask.create({
            'property_id': self.property.id,
            'space_id': self.space.id,
            'business_date': Date.today(),
            'task_type': task_type,
        })

    def test_drag_pending_to_in_progress_calls_action_assign(self):
        """Dragging a card from Pending to In Progress with an
        attendant already set on the card goes through
        action_assign(): state changes AND started_at gets stamped,
        proving the action method ran rather than a bare write."""
        task = self._create_task()
        task.attendant_user_id = self.attendant_user
        self.assertFalse(task.started_at)

        task.write({'state': 'in_progress'})

        self.assertEqual(task.state, 'in_progress')
        self.assertTrue(task.started_at)

    def test_drag_in_progress_to_done_calls_action_finish(self):
        """Dragging In Progress -> Done stamps finished_at, proving
        it went through action_finish()."""
        task = self._create_task()
        task.action_assign(attendant_user_id=self.attendant_user.id)

        task.write({'state': 'done'})

        self.assertEqual(task.state, 'done')
        self.assertTrue(task.finished_at)

    def test_drag_done_to_inspected_updates_space_status(self):
        """Dragging Done -> Inspected on a departure task must also
        run action_inspect()'s space-status side effect, not just
        flip the state column."""
        task = self._create_task(task_type='departure')
        task.action_assign(attendant_user_id=self.attendant_user.id)
        task.action_finish()

        task.write({'state': 'inspected'})

        self.assertEqual(task.state, 'inspected')
        self.assertEqual(task.space_id.status, 'vacant_clean')
        self.assertTrue(task.inspected_at)

    def test_drag_unassigned_pending_to_in_progress_raises(self):
        """Dragging an unassigned card to In Progress must still
        fail the way action_assign() would: it can't leave both
        attendant fields empty."""
        task = self._create_task()
        with self.assertRaises(UserError):
            task.write({'state': 'in_progress'})

    def test_drag_invalid_transition_raises(self):
        """A drag between two columns that isn't a valid transition
        (e.g. straight from Pending to Done, skipping In Progress)
        is rejected rather than silently accepted."""
        task = self._create_task()
        with self.assertRaises(UserError):
            task.write({'state': 'done'})

    def test_form_style_write_bypasses_drag_routing(self):
        """A write touching state alongside other fields (as a form
        save, or wizard, would send) is not intercepted -- this
        confirms the special-casing is scoped to the bare
        {'state': ...} shape a kanban drag produces."""
        task = self._create_task()
        task.write({'state': 'in_progress', 'notes': 'Manual override'})
        self.assertEqual(task.state, 'in_progress')
        self.assertEqual(task.notes, 'Manual override')