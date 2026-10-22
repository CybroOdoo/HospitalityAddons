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
from odoo import fields, models
from odoo.tools import _

STEP_CHOICES = [
    ('validate_checkouts', 'Validate Checkouts'),
    ('mark_no_shows', 'Mark No-Shows'),
    ('post_room_charges', 'Post Room Charges'),
    ('post_package_inclusions', 'Post Package Inclusions'),
    ('post_in_house_deposits', 'Post In-House Deposits'),
    ('reconcile_hk_pms', 'Reconcile Housekeeping / PMS'),
    ('close_cashier_shifts', 'Close Cashier Shifts'),
    ('generate_reports', 'Generate Reports'),
    ('advance_business_date', 'Advance Business Date'),
    ('lock_period', 'Lock Period'),
    ('reconcile_journal', 'Reconcile Journal'),
]


class HospitalityNightAuditStep(models.Model):
    """
    Night audit step model for tracking the execution of individual
    night audit operations.
    """
    _name = 'hospitality.night.audit.step'
    _description = 'Hospitality Night Audit Step'
    _order = 'sequence, id'

    run_id = fields.Many2one(
        comodel_name='hospitality.night.audit.run',
        string='Audit Run',
        required=True,
        ondelete='cascade',
        index=True,
        help="The parent night audit run that this step belongs to. "
             "Steps are cascade-deleted when their parent run is deleted.",
    )
    sequence = fields.Integer(
        string='Sequence',
        required=True,
        default=10,
        help="Ordering of steps within the audit run. Lower numbers execute first.",
    )
    name = fields.Selection(
        selection=STEP_CHOICES,
        string='Step',
        required=True,
        help="The type of audit operation this step performs. Each step type "
             "has a corresponding `_step_<name>` method on the run model.",
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('ok', 'OK'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        string='Status',
        required=True,
        default='pending',
        help="Current execution status of this step: Pending (not yet executed), "
             "OK (completed successfully), Failed (execution error), or "
             "Skipped (intentionally bypassed).",
    )
    message = fields.Text(
        string='Message',
        help="Detailed result message from step execution, including success "
             "confirmations, warnings, or error details.",
    )
    started_at = fields.Datetime(
        string='Started At',
        help="Timestamp when this step began execution.",
    )
    ended_at = fields.Datetime(
        string='Ended At',
        help="Timestamp when this step completed execution.",
    )

    def action_execute(self):
        """Idempotent execution entry point. A step already marked 'ok'
        is a no-op — combined with `_resume()` on the run, this is what
        guarantees a resumed audit doesn't double-post.

        NA-03: the real per-step business logic lives on the run model
        as `_step_<name>()` methods returning a (status, message) tuple
        (see hospitality_night_audit_run.py). This method is the
        orchestrator: it calls `_run()` (which dispatches to the right
        `_step_<name>` method), then writes the returned status/message
        onto this step row.
        """
        for step in self:
            if step.status == 'ok':
                continue
            step.started_at = fields.Datetime.now()
            try:
                if step._is_already_applied():
                    step.write({
                        'status': 'ok',
                        'message': _('Already applied for this business date — skipped.'),
                        'ended_at': fields.Datetime.now(),
                    })
                    continue
                status, message = step._run()
                step.write({
                    'status': status or 'ok',
                    'message': message or False,
                    'ended_at': fields.Datetime.now(),
                })
            except Exception as exc:
                step.write({
                    'status': 'failed',
                    'message': str(exc),
                    'ended_at': fields.Datetime.now(),
                })
        return True

    def _is_already_applied(self):
        """Coarse, step-level "already done" check. Default is always
        False — NA-03's individual `_step_<name>()` methods each do
        their own fine-grained idempotency check internally (e.g.
        `_step_post_room_charges` looks up existing folio lines for
        run.business_date before posting), which is more precise than a
        single boolean here. This hook is kept for cases where a
        coarse, step-wide skip is genuinely correct and cheaper than
        entering the method at all; it is not used by NA-03's steps
        today.
        """
        self.ensure_one()
        return False

    def _run(self):
        """Dispatch to `hospitality.night.audit.run._step_<name>()`,
        which implements the concrete business logic and returns a
        (status, message) tuple. Kept as a thin, separately-patchable
        method (rather than inlining the dispatch into action_execute)
        so it stays easy to mock in tests — see
        test_resume_skips_already_completed_steps in NA-02's test
        suite, which patches this exact method.
        """
        self.ensure_one()
        method_name = '_step_%s' % self.name
        method = getattr(self.run_id, method_name, None)
        if method is None:
            return (
                'skipped',
                _('No handler implemented for step "%s".') % self.name,
            )
        return method()