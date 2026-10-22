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

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNightAuditRun(TransactionCase):
    """NA-02: audit run + step models + idempotency."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'NA-02 Test Property',
            'code': 'NA02',
        })
        cls.today = fields.Date.today()

    def test_unique_run_per_property_per_date(self):
        Run = self.env['hospitality.night.audit.run']
        Run.create({
            'property_id': self.property.id,
            'business_date': self.today,
        })
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                Run.create({
                    'property_id': self.property.id,
                    'business_date': self.today,
                })
                self.env.flush_all()

    def test_step_lifecycle(self):
        run = self.env['hospitality.night.audit.run'].create({
            'property_id': self.property.id,
            'business_date': self.today,
        })
        run._prepare_steps()
        self.assertEqual(len(run.step_ids), len(run._STEP_DEFINITIONS))

        first_step = run.step_ids.sorted('sequence')[0]
        self.assertEqual(first_step.status, 'pending')
        self.assertFalse(first_step.started_at)

        first_step.action_execute()
        self.assertEqual(first_step.status, 'ok')
        self.assertTrue(first_step.started_at)
        self.assertTrue(first_step.ended_at)

        # Re-executing an already-'ok' step is a no-op.
        prev_ended_at = first_step.ended_at
        first_step.action_execute()
        self.assertEqual(first_step.ended_at, prev_ended_at)

    def test_resume_skips_already_completed_steps(self):
        StepModel = self.env.registry['hospitality.night.audit.step']

        run = self.env['hospitality.night.audit.run'].create({
            'property_id': self.property.id,
            'business_date': self.today,
        })
        run._prepare_steps()
        steps = run.step_ids.sorted('sequence')

        # Simulate a previous partial run: the first step already
        # completed, the rest still pending.
        completed_step = steps[0]
        completed_step.write({
            'status': 'ok',
            'started_at': fields.Datetime.now(),
            'ended_at': fields.Datetime.now(),
            'message': 'Completed in a previous run.',
        })
        remaining_count = len(steps) - 1
        run.state = 'error'

        # NA-03: `_run()` now returns a (status, message) tuple (the
        # orchestrator contract used to dispatch to the run model's
        # `_step_<name>()` methods), so the mock must return one too —
        # an unconfigured MagicMock isn't unpackable and would break
        # `status, message = step._run()` in action_execute.
        with patch.object(
            StepModel, '_run', autospec=True, return_value=('ok', 'stub'),
        ) as mock_run:
            run._resume()

        # Only the non-'ok' steps should have been executed.
        self.assertEqual(mock_run.call_count, remaining_count)
        # The already-completed step must be untouched.
        self.assertEqual(completed_step.message, 'Completed in a previous run.')
        self.assertEqual(run.state, 'posted')