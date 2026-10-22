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
from datetime import datetime
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNightAuditWizard(TransactionCase):
    """NA-04: audit wizard UI (Start/Resume/Force Close) + auto-start cron."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.property = cls.env['hospitality.property'].create({
            'name': 'NA-04 Test Property',
            'code': 'NA04',
        })
        cls.today = fields.Date.today()

        base_group_user = cls.env.ref('base.group_user')
        auditor_group = cls.env.ref('hospitality_night_audit.group_night_auditor')
        supervisor_group = cls.env.ref('hospitality_night_audit.group_night_audit_supervisor')

        cls.auditor_user = cls.env['res.users'].create({
            'name': 'NA-04 Auditor',
            'login': 'na04_auditor',
            'group_ids': [(6, 0, [base_group_user.id, auditor_group.id])],
        })
        cls.supervisor_user = cls.env['res.users'].create({
            'name': 'NA-04 Supervisor',
            'login': 'na04_supervisor',
            'group_ids': [(6, 0, [base_group_user.id, supervisor_group.id])],
        })

        # hospitality_base.hospitality.property.write() gates
        # business_date behind `self.env.user.has_group(
        # 'hospitality_base.group_hospitality_admin')` — checked on
        # env.user directly, so sudo() does NOT bypass it (see
        # hospitality_night_audit_run._step_advance_business_date's
        # docstring). The cron tests below write business_date
        # directly to set up their fixture property, so the test's
        # acting user needs that group, same as a real supervisor
        # would.
        admin_group = cls.env.ref(
            'hospitality_base.group_hospitality_admin', raise_if_not_found=False,
        )
        if admin_group:
            cls.env.user.write({'group_ids': [(4, admin_group.id)]})

    def test_start_audit_runs_all_steps(self):
        run = self.env['hospitality.night.audit.run'].create({
            'property_id': self.property.id,
            'business_date': self.today,
        })
        self.assertEqual(run.state, 'draft')

        run.action_start()

        self.assertEqual(len(run.step_ids), len(run._STEP_DEFINITIONS))
        self.assertTrue(
            all(step.status != 'pending' for step in run.step_ids),
            'action_start should have executed every step at least once.',
        )
        # A fresh property with no reservations/txn codes can validly
        # end in 'error' (e.g. the ROOM transaction code step) — what
        # matters here is that orchestration actually ran, not that
        # every step happened to succeed.
        self.assertIn(run.state, ('posted', 'error'))

        # Starting a non-draft run is rejected.
        with self.assertRaises(Exception):
            run.action_start()

    def test_resume_runs_only_failed_steps(self):
        StepModel = self.env.registry['hospitality.night.audit.step']

        run = self.env['hospitality.night.audit.run'].create({
            'property_id': self.property.id,
            'business_date': self.today,
        })
        run._prepare_steps()
        steps = run.step_ids.sorted('sequence')

        # Simulate a previous partial run: first step already 'ok',
        # the rest still pending.
        completed_step = steps[0]
        completed_step.write({
            'status': 'ok',
            'started_at': fields.Datetime.now(),
            'ended_at': fields.Datetime.now(),
            'message': 'Completed in a previous run.',
        })
        remaining_count = len(steps) - 1
        run.state = 'error'

        with patch.object(
            StepModel, '_run', autospec=True, return_value=('ok', 'stub'),
        ) as mock_run:
            run.action_resume()

        self.assertEqual(mock_run.call_count, remaining_count)
        self.assertEqual(completed_step.message, 'Completed in a previous run.')
        self.assertEqual(run.state, 'posted')

        # Resuming a draft run is rejected.
        draft_run = self.env['hospitality.night.audit.run'].create({
            'property_id': self.property.id,
            'business_date': fields.Date.add(self.today, days=1),
        })
        with self.assertRaises(Exception):
            draft_run.action_resume()

    def test_cron_starts_audit_when_auto_audit_true(self):
        self.property.write({
            'auto_audit': True,
            'business_date': self.today,
        })
        Run = self.env['hospitality.night.audit.run']
        self.assertFalse(Run.search([
            ('property_id', '=', self.property.id),
            ('business_date', '=', self.today),
        ]))

        # Property has no confirmable tz field in this test env, so
        # _get_audit_tz() falls back to UTC — freeze "now" to 03:00
        # UTC, safely past the 02:00 threshold.
        fixed_now = datetime.combine(self.today, datetime.min.time()).replace(hour=3)
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            Run._cron_auto_start_night_audit()

        created = Run.search([
            ('property_id', '=', self.property.id),
            ('business_date', '=', self.today),
        ])
        self.assertTrue(created, 'Cron should have created a run for the auto_audit property.')
        self.assertIn(created.state, ('posted', 'error'))

        # Re-running the cron for the same hour must not create a
        # second run for the same property/date.
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            Run._cron_auto_start_night_audit()
        self.assertEqual(len(Run.search([
            ('property_id', '=', self.property.id),
            ('business_date', '=', self.today),
        ])), 1)

    def test_cron_skips_before_2am_local(self):
        self.property.write({'auto_audit': True, 'business_date': self.today})
        Run = self.env['hospitality.night.audit.run']

        fixed_now = datetime.combine(self.today, datetime.min.time()).replace(hour=1)
        with patch('odoo.fields.Datetime.now', return_value=fixed_now):
            Run._cron_auto_start_night_audit()

        self.assertFalse(Run.search([
            ('property_id', '=', self.property.id),
            ('business_date', '=', self.today),
        ]), 'Cron should not start an audit before 02:00 local time.')

    def test_force_close_supervisor_only(self):
        run = self.env['hospitality.night.audit.run'].create({
            'property_id': self.property.id,
            'business_date': self.today,
        })

        with self.assertRaises(AccessError):
            run.with_user(self.auditor_user).action_force_close()
        self.assertNotEqual(run.state, 'closed')

        run.with_user(self.supervisor_user).action_force_close()
        self.assertEqual(run.state, 'closed')