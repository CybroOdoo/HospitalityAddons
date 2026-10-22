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
import base64
from ast import literal_eval
from datetime import time as dtime, timedelta

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from .hospitality_night_audit_step import STEP_CHOICES


class HospitalityNightAuditRun(models.Model):
    """Stores and executes a hospitality night audit run."""
    _name = 'hospitality.night.audit.run'
    _description = 'Hospitality Night Audit Run'
    _inherit = ['mail.thread']
    _order = 'started_at desc'

    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default=lambda self: self.env._('New'),
        help="Unique reference/sequence number for this audit run.",
    )
    property_id = fields.Many2one(
        comodel_name='hospitality.property',
        string='Property',
        required=True,
        index=True,
        help="The hospitality property for which this night audit is being run.",
    )
    business_date = fields.Date(
        string='Business Date',
        required=True,
        help="The business date being audited. This is the date for which all "
             "transactions and reservations are being processed.",
    )
    started_at = fields.Datetime(
        string='Started At',
        default=fields.Datetime.now,
        help="Timestamp when this audit run was initiated.",
    )
    ended_at = fields.Datetime(
        string='Ended At',
        help="Timestamp when this audit run completed (either successfully or with errors).",
    )
    run_by = fields.Many2one(
        comodel_name='res.users',
        string='Run By',
        default=lambda self: self.env.user,
        help="User who initiated or executed this audit run.",
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('posted', 'Posted'),
            ('closed', 'Closed'),
            ('error', 'Error'),
        ],
        string='Status',
        required=True,
        default='draft',
        tracking=True,
        help="Current state of the audit run: Draft (not yet started), "
             "In Progress (executing steps), Posted (all steps completed successfully), "
             "Closed (manually closed/finalized), or Error (one or more steps failed).",
    )
    step_ids = fields.One2many(
        comodel_name='hospitality.night.audit.step',
        inverse_name='run_id',
        string='Steps',
        help="The individual audit steps that make up this run, each with its "
             "own status and execution results.",
    )
    log_text = fields.Text(
        string='Log',
        help="Consolidated log of messages, warnings, and errors from all "
             "steps executed during this audit run.",
    )
    reservation_no_shows = fields.Integer(
        string='No-Shows Processed',
        default=0,
        help="Total number of reservations marked as no-show during this audit run.",
    )
    rooms_posted = fields.Integer(
        string='Rooms Posted',
        default=0,
        help="Total number of room charge lines posted during this audit run.",
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help="Currency used for monetary amounts in this audit run.",
    )
    taxes_posted = fields.Monetary(
        string='Taxes Posted',
        currency_field='currency_id',
        default=0.0,
        help="Total amount of taxes posted during this audit run.",
    )
    variance_report_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='Variance Report',
        help="Attachment containing the variance report generated during this "
             "audit run, showing discrepancies between housekeeping status "
             "and PMS occupancy.",
    )
    next_business_date = fields.Date(
        string='Next Business Date',
        compute='_compute_next_business_date',
        store=True,
        help="The next business date, computed as business_date + 1 day. "
             "Used when advancing the property's business date.",
    )

    _STEP_DEFINITIONS = [code for code, _label in STEP_CHOICES]

    @api.depends('business_date')
    def _compute_next_business_date(self):
        """Compute the next business date."""
        for run in self:
            run.next_business_date = (
                run.business_date + timedelta(days=1)
                if run.business_date else False
            )

    def _auto_init(self):
        """Create the unique index for property and business date."""
        res = super()._auto_init()
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            hospitality_night_audit_run_property_date_uniq
            ON hospitality_night_audit_run (property_id, business_date)
        """)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Generate a sequence for new audit runs."""
        new_label = self.env._('New')
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == new_label:
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hospitality.night.audit.run'
                ) or new_label
        return super().create(vals_list)

    def _get_step_definitions(self):
        """Hook for later tickets to extend/override the ordered list of
        step codes prepared for a fresh audit run."""
        self.ensure_one()
        return list(self._STEP_DEFINITIONS)

    def _prepare_steps(self):
        """Create step_ids for a fresh run, one per definition. No-op if
        steps already exist, so calling this again on resume is safe."""
        self.ensure_one()
        if self.step_ids:
            return self.step_ids
        Step = self.env['hospitality.night.audit.step']
        steps = Step
        for index, code in enumerate(self._get_step_definitions(), start=1):
            steps |= Step.create({
                'run_id': self.id,
                'sequence': index * 10,
                'name': code,
            })
        return steps

    def action_start(self):
        """NA-04 'Start Audit' button. Only valid from state='draft' —
        prepares the step list and runs the full orchestration. To
        re-run outstanding steps on an already-started run, use
        action_resume() instead (kept as a separate method so the
        form view can show the right button for the run's current
        state, even though `_resume()` itself already skips any step
        marked 'ok' either way).
        """
        for run in self:
            if run.state != 'draft':
                raise UserError(
                    "Only a draft audit run can be started. Run "
                    "%(name)s is already '%(state)s' — use Resume "
                    "instead to re-run its outstanding steps."
                 % {'name': run.name, 'state': run.state})
            run._prepare_steps()
            run._resume()
        return True

    def action_resume(self):
        """NA-04 'Resume' button — re-runs only failed/pending steps
        on a run that's already in progress or errored out. Thin
        wrapper around `_resume()`.
        """
        for run in self:
            if run.state not in ('in_progress', 'error'):
                raise UserError(
                    "Only an in-progress or errored audit run can be "
                    "resumed. Run %(name)s is '%(state)s'."
                 % {'name': run.name, 'state': run.state})
            run._resume()
        return True

    def action_force_close(self):
        """NA-04 'Force Close' button — supervisor override. Sets
        state='closed' regardless of any outstanding step failures.
        Restricted to the Night Audit Supervisor group; checked here
        (not just via the button's `groups` attribute in the form
        view) since this method could otherwise be reached directly,
        e.g. via a server action or RPC. Always posted to the
        chatter so the override is audit-logged.
        """
        for run in self:
            if not self.env.user.has_group(
                'hospitality_night_audit.group_night_audit_supervisor'
            ):
                raise AccessError(
                    'Only a Night Audit Supervisor can force-close an '
                    'audit run.'
                )
            run.message_post(body=
                'Audit run force-closed by %(user)s, bypassing any '
                'outstanding step failures.'
             % {'user': self.env.user.name})
            run.write({
                'state': 'closed',
                'ended_at': fields.Datetime.now(),
            })
        return True

    @api.model
    def action_open_property_runs(self):
        """Menu entry point for 'Night Audit' — opens the run list,
        filtered to the acting user's current property when one can
        be determined."""
        action = self.env['ir.actions.act_window']._for_xml_id(
            'hospitality_night_audit.action_night_audit_run'
        )
        property_ids = self._get_current_property_ids()
        if property_ids:
            action['domain'] = [('property_id', 'in', property_ids)]
            raw_context = action.get('context') or {}
            if isinstance(raw_context, str):
                raw_context = literal_eval(raw_context) if raw_context.strip() else {}
            action['context'] = dict(
                raw_context,
                default_property_id=property_ids[0],
                search_default_property_id=property_ids[0],
            )
        return action

    @api.model
    def _get_current_property_ids(self):
        """Best-effort resolution of the acting user's current
        property. See the GAP note above this method's caller."""
        user = self.env.user
        for field_name in ('property_id', 'current_property_id', 'default_property_id'):
            if field_name in user._fields:
                value = getattr(user, field_name)
                if value:
                    return value.ids
        for field_name in ('property_ids', 'allowed_property_ids'):
            if field_name in user._fields:
                value = getattr(user, field_name)
                if value:
                    return value.ids
        return []

    @api.model
    def _cron_auto_start_night_audit(self):
        """Hourly cron (see data/ir_cron.xml). For every property with
        auto_audit=True, once local time is past 02:00 on that
        property's current business_date and no run exists yet for
        that date, create and start one — reusing run_audit() so
        there's no separate creation path to keep in sync with the
        manual wizard.
        """
        properties = self.env['hospitality.property'].search([
            ('auto_audit', '=', True),
        ])
        now_utc = pytz.UTC.localize(fields.Datetime.now())
        for property_ in properties:
            business_date = property_.business_date or fields.Date.context_today(self)

            tz_name = property_._get_audit_tz() if hasattr(property_, '_get_audit_tz') else 'UTC'
            try:
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = pytz.UTC
            local_now = now_utc.astimezone(tz)
            if local_now.time() < dtime(2, 0):
                continue  # not past 02:00 local time yet

            existing = self.search([
                ('property_id', '=', property_.id),
                ('business_date', '=', business_date),
            ], limit=1)
            if existing:
                continue

            self.run_audit(property_.id, business_date)
        return True

    def _resume(self):
        """Re-run any steps not yet marked 'ok'. Steps already completed
        are left untouched — this is what makes re-running an audit for
        the same business date safe against double-posting."""
        for run in self:
            if run.state not in ('draft', 'in_progress', 'error'):
                continue
            run.state = 'in_progress'
            has_failure = False
            for step in run.step_ids.sorted('sequence'):
                if step.status == 'ok':
                    continue
                step.action_execute()
                if step.status == 'failed':
                    has_failure = True
            run.ended_at = fields.Datetime.now()
            run.state = 'error' if has_failure else 'posted'
        return True

    @api.model
    def run_audit(self, property_id, business_date):
        """Public entry point: reuses an existing run for the same
        property/date instead of creating a duplicate. The DB-level
        unique index in `_auto_init` is the hard backstop for this."""
        existing = self.search([
            ('property_id', '=', property_id),
            ('business_date', '=', business_date),
        ], limit=1)
        if existing:
            existing._resume()
            return existing
        run = self.create({
            'property_id': property_id,
            'business_date': business_date,
        })
        run._prepare_steps()
        run._resume()
        return run

    def _step_validate_checkouts(self):
        """1. Assert every expected departure for business_date is
        either checked_out, no_show, or has a folio in state
        'transferred_ar'. Reservations that fail this are collected
        into the failure list; the step fails (rather than silently
        continuing) so a human has to look at the log before the audit
        completes.
        """
        self.ensure_one()
        Reservation = self.env['hospitality.reservation']
        Folio = self.env['hospitality.folio']

        expected = Reservation.search([
            ('property_id', '=', self.property_id.id),
            ('departure', '=', self.business_date),
            ('state', 'not in', ('draft', 'option', 'cancelled')),
        ])

        failures = []
        for res in expected:
            if res.state in ('checked_out', 'no_show'):
                continue
            transferred = Folio.search_count([
                ('reservation_id', '=', res.id),
                ('state', '=', 'transferred_ar'),
            ])
            if transferred:
                continue
            failures.append(res.name)

        if failures:
            message = (
                'Unresolved departures for %(date)s: %(names)s'
            ) % {'date': self.business_date, 'names': ', '.join(failures)}
            self.log_text = '%s\n%s' % (self.log_text or '', message)
            return ('failed', message)

        return (
            'ok',
            'All %(count)d expected departure(s) resolved.' % {
                'count': len(expected)
            },
        )

    def _step_mark_no_shows(self):
        """2. For confirmed reservations whose arrival is business_date
        and who never checked in, set is_no_show=True, state=no_show,
        and apply a cancellation-policy charge if the guarantee type
        requires one (credit_card / deposit guarantees are treated as
        chargeable; 'none' has nothing to charge against).

        Naturally idempotent: once marked, a reservation's state is no
        longer 'confirmed', so re-running this step won't find it
        again via the search domain below.
        """
        self.ensure_one()
        Reservation = self.env['hospitality.reservation']
        candidates = Reservation.search([
            ('property_id', '=', self.property_id.id),
            ('arrival', '=', self.business_date),
            ('state', '=', 'confirmed'),
        ])

        marked = []
        for res in candidates:
            res.write({'is_no_show': True, 'state': 'no_show'})
            if (
                res.guarantee_type in ('credit_card', 'deposit')
                and res.cancellation_policy_id
                and hasattr(res.cancellation_policy_id, 'compute_charge')
            ):
                try:
                    res.cancellation_policy_id.compute_charge(res)
                except Exception:
                    pass
            marked.append(res.name)
            self.reservation_no_shows += 1

        if marked:
            return ('ok', 'Marked no-show: %s' % ', '.join(marked))
        return ('ok', 'No arrivals to mark as no-show.')

    def _step_post_room_charges(self):
        """3. For in-house (checked_in) guests, post a ROOM line via
        folio._post_charge() using rate_code._get_rate()'s nightly
        price for business_date.

        Idempotent per-reservation: before posting, checks for an
        existing, non-voided ROOM line on the folio dated
        business_date and skips if found — this is the exact
        idempotency pattern described in the NA-02 spec ("looks up
        existing folio lines with business_date == run.business_date
        and skips if found").

        NOTE: hospitality.folio._post_charge() does not accept a
        business_date kwarg in its current signature, so this writes
        business_date onto the created line explicitly afterward
        (guarded by a field-existence check) to guarantee it matches
        this run's business_date rather than whatever the line model's
        own default resolves to.

        NOTE: window_seq=1 is passed explicitly to force room charges
        onto the primary folio window, bypassing
        hospitality.routing.instruction evaluation. Room charges have
        no special routing requirement per this spec, and forcing
        window 1 avoids depending on routing-rule data that may not be
        configured on every property.
        """
        self.ensure_one()
        Reservation = self.env['hospitality.reservation']
        TxnCode = self.env['hospitality.transaction.code']
        Line = self.env['hospitality.folio.line']

        room_code = TxnCode.search([('code', '=', 'ROOM')], limit=1)
        if not room_code:
            return ('failed', 'No transaction code with code "ROOM" found.')

        # In-house guests. "Today's arrivals" who are not yet checked in
        # have no room to charge for yet; guests who arrived today and
        # are already checked_in are covered by this same domain.
        candidates = Reservation.search([
            ('property_id', '=', self.property_id.id),
            ('state', '=', 'checked_in'),
        ])

        posted = 0
        for res in candidates:
            if 'folio_ids' not in res._fields or not res.folio_ids:
                continue
            folio = res.folio_ids[:1]

            already = Line.search_count([
                ('folio_id', '=', folio.id),
                ('transaction_code_id', '=', room_code.id),
                ('business_date', '=', self.business_date),
                ('is_void', '=', False),
            ])
            if already:
                continue  # idempotent skip — already posted for this date

            try:
                rate_result = res.rate_code_id._get_rate(
                    self.property_id.id,
                    res.space_type_id.id,
                    res.rate_code_id.id,
                    self.business_date,
                    self.business_date + timedelta(days=1),
                    {'adults': res.adults, 'children': res.children},
                )
            except Exception as exc:
                return (
                    'failed',
                    'Rate lookup failed for %(name)s: %(err)s' % {
                        'name': res.name, 'err': exc,
                    },
                )

            nightly = rate_result.get('nightly') or []
            price = nightly[0][1] if nightly else None
            if price is None:
                continue  # no rate plan for this date — nothing to post

            line = folio._post_charge(
                transaction_code_id=room_code,
                qty=1,
                price=price,
                ref='Room charge — %s' % self.business_date,
                source_model='hospitality.reservation',
                source_id=res.id,
                window_seq=1,
            )
            if line and 'business_date' in line._fields:
                line.business_date = self.business_date

            posted += 1
            self.rooms_posted += 1
            self.taxes_posted += line.tax_amount

        return ('ok', 'Posted %(count)d room charge line(s).' % {'count': posted})

    def _step_post_package_inclusions(self):
        """4. Expand package inclusions per rate_code.package_id and
        post them via their transaction codes, reusing the
        `inclusions` list already returned by rate_code._get_rate()
        (built from hospitality.package.inclusion in RATE-06 — no
        separate package-expansion logic needed here).

        Idempotent per-line: checks for an existing non-voided line on
        the folio for (transaction_code, business_date) before
        posting.
        """
        self.ensure_one()
        Reservation = self.env['hospitality.reservation']
        Line = self.env['hospitality.folio.line']
        TxnCode = self.env['hospitality.transaction.code']

        candidates = Reservation.search([
            ('property_id', '=', self.property_id.id),
            ('state', '=', 'checked_in'),
        ])

        posted = 0
        for res in candidates:
            if not res.rate_code_id or not res.rate_code_id.package_id:
                continue
            if 'folio_ids' not in res._fields or not res.folio_ids:
                continue
            folio = res.folio_ids[:1]

            try:
                rate_result = res.rate_code_id._get_rate(
                    self.property_id.id,
                    res.space_type_id.id,
                    res.rate_code_id.id,
                    self.business_date,
                    self.business_date + timedelta(days=1),
                    {'adults': res.adults, 'children': res.children},
                )
            except Exception as exc:
                return (
                    'failed',
                    'Package inclusion lookup failed for %(name)s: %(err)s' % {
                        'name': res.name, 'err': exc,
                    },
                )

            for incl in rate_result.get('inclusions') or []:
                tc_id = incl.get('transaction_code_id')
                if not tc_id:
                    continue

                already = Line.search_count([
                    ('folio_id', '=', folio.id),
                    ('transaction_code_id', '=', tc_id),
                    ('business_date', '=', self.business_date),
                    ('is_void', '=', False),
                ])
                if already:
                    continue

                txn_code = TxnCode.browse(tc_id)
                line = folio._post_charge(
                    transaction_code_id=txn_code,
                    qty=incl.get('qty', 1),
                    price=incl.get('value', 0.0),
                    ref='Package inclusion — %s' % self.business_date,
                    source_model='hospitality.reservation',
                    source_id=res.id,
                    window_seq=1,
                )
                if line and 'business_date' in line._fields:
                    line.business_date = self.business_date
                posted += 1
                self.taxes_posted += line.tax_amount

        return ('ok', 'Posted %(count)d package inclusion line(s).' % {'count': posted})

    def _step_post_in_house_deposits(self):
        """5. Carry forward held deposits for in-house guests.

        ASSUMPTION: held deposits are not date-scoped folio lines —
        they persist on the folio across business dates without
        needing an explicit "post" action, so there is nothing to
        write here without inventing new API surface on
        hospitality.deposit that isn't part of this spec. This step
        instead confirms/logs how many are still held (guarded by a
        'state' field-existence check, since hospitality.deposit's
        exact fields weren't available when this was written — only
        its presence as folio.deposit_ids was known).
        """
        self.ensure_one()
        Reservation = self.env['hospitality.reservation']
        in_house = Reservation.search([
            ('property_id', '=', self.property_id.id),
            ('state', '=', 'checked_in'),
        ])

        held_count = 0
        for res in in_house:
            if 'folio_ids' not in res._fields:
                continue
            for folio in res.folio_ids:
                deposits = getattr(folio, 'deposit_ids', None)
                if not deposits:
                    continue
                for dep in deposits:
                    if 'state' in dep._fields and dep.state == 'held':
                        held_count += 1

        return ('ok', '%(count)d held deposit(s) carried forward.' % {'count': held_count})

    def _step_reconcile_hk_pms(self):
        """6. Compare hospitality.space.status against actual in-house
        reservation occupancy; produce a discrepancy attachment linked
        to this run.

        Idempotent: checks for an already-generated attachment for
        this run + business_date before creating another.
        """
        self.ensure_one()
        Attachment = self.env['ir.attachment']
        attachment_name = 'HK-PMS Reconciliation %s.txt' % self.business_date

        existing = Attachment.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('name', '=', attachment_name),
        ], limit=1)
        if existing:
            return (
                'ok',
                'Reconciliation already generated for %(date)s (see attachment %(name)s).' % {
                    'date': self.business_date, 'name': existing.name,
                },
            )

        Space = self.env['hospitality.space']
        Reservation = self.env['hospitality.reservation']

        spaces = Space.search([('property_id', '=', self.property_id.id)])
        occupied_space_ids = set(Reservation.search([
            ('property_id', '=', self.property_id.id),
            ('state', '=', 'checked_in'),
            ('space_id', '!=', False),
        ]).mapped('space_id').ids)

        occupied_statuses = {'occupied_clean', 'occupied_dirty'}
        discrepancies = []
        for space in spaces:
            is_occupied_in_pms = space.id in occupied_space_ids
            is_marked_occupied = space.status in occupied_statuses
            if is_occupied_in_pms != is_marked_occupied:
                discrepancies.append(
                    '%s: PMS says %s, housekeeping status is "%s"' % (
                        space.code,
                        'occupied' if is_occupied_in_pms else 'vacant',
                        space.status,
                    )
                )

        content = 'Housekeeping / PMS reconciliation — %s\n%s\n\n' % (
            self.property_id.display_name, self.business_date,
        )
        if discrepancies:
            content += 'Discrepancies (%d):\n' % len(discrepancies)
            content += '\n'.join(discrepancies)
        else:
            content += 'No discrepancies found.'

        attachment = Attachment.create({
            'name': attachment_name,
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/plain',
        })

        if discrepancies:
            return (
                'ok',
                '%(count)d discrepancy(ies) found — see attachment %(name)s.' % {
                    'count': len(discrepancies), 'name': attachment.name,
                },
            )
        return ('ok', 'No housekeeping/PMS discrepancies found.')

    def _step_close_cashier_shifts(self):
        """7. For cashier/front-desk shifts on business_date still
        open, attempt an auto-close (with an audit warning if a
        specific shift fails to close cleanly).

        GAP: the cashier/front-desk shift model from FD-06 was not
        available when this was written — only its existence was
        mentioned ("FD Shift"), not its actual model name or fields.
        Guessing wrong here would silently break at runtime rather
        than fail loudly, so this defensively probes a short list of
        plausible model names and no-ops (status='skipped') if none
        are installed, rather than hardcoding one that might not
        exist. Replace the `for candidate in (...)` list below with
        the real model name once confirmed, and drop the probing.
        """
        self.ensure_one()
        Shift = None
        for candidate in (
            'hospitality.front.desk.shift',
            'hospitality.cashier.shift',
            'hospitality.shift',
        ):
            if candidate in self.env:
                Shift = self.env[candidate]
                break

        if Shift is None:
            return ('skipped', 'Cashier shift model not found — step skipped.')

        domain = [('property_id', '=', self.property_id.id)]
        if 'state' in Shift._fields:
            domain.append(('state', '=', 'open'))
        open_shifts = Shift.search(domain)

        closed = 0
        warnings = []
        for shift in open_shifts:
            try:
                if hasattr(shift, 'action_close'):
                    shift.action_close()
                elif 'state' in shift._fields:
                    shift.write({'state': 'closed'})
                closed += 1
            except Exception as exc:
                warnings.append('%s: %s' % (shift.display_name, exc))

        message = '%(count)d shift(s) auto-closed.' % {'count': closed}
        if warnings:
            message += ' ' + 'Warnings: %s' % '; '.join(warnings)
        return ('ok', message)

    def _step_generate_reports(self):
        """8. Produce the report bundle (daily revenue, occupancy,
        arrivals/departures/no-shows, manager flash) and save it as an
        ir.attachment linked to this run.

        GAP: no QWeb report templates for these reports exist in this
        codebase yet. Rather than reference report actions that don't
        exist (which would raise ValueError at runtime), this
        generates a plain-text stand-in summarizing the same KPIs from
        data this module can already query directly. Replace the
        `content = (...)` block below with real
        `report_action().render_qweb_pdf()` calls once those templates
        are built — the surrounding idempotency/attachment-linking
        logic won't need to change.

        Also populates variance_report_id on the run, satisfying that
        field's purpose (see NA-02).
        """
        self.ensure_one()
        Attachment = self.env['ir.attachment']
        attachment_name = 'Night Audit Report %s.txt' % self.business_date

        existing = Attachment.search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('name', '=', attachment_name),
        ], limit=1)
        if existing:
            self.variance_report_id = existing.id
            return (
                'ok',
                'Reports already generated for %(date)s (see attachment %(name)s).' % {
                    'date': self.business_date, 'name': existing.name,
                },
            )

        Reservation = self.env['hospitality.reservation']
        Space = self.env['hospitality.space']

        arrivals = Reservation.search_count([
            ('property_id', '=', self.property_id.id),
            ('arrival', '=', self.business_date),
        ])
        departures = Reservation.search_count([
            ('property_id', '=', self.property_id.id),
            ('departure', '=', self.business_date),
        ])
        no_shows = Reservation.search_count([
            ('property_id', '=', self.property_id.id),
            ('arrival', '=', self.business_date),
            ('state', '=', 'no_show'),
        ])
        in_house = Reservation.search_count([
            ('property_id', '=', self.property_id.id),
            ('state', '=', 'checked_in'),
        ])
        total_spaces = Space.search_count([
            ('property_id', '=', self.property_id.id),
        ])
        occupancy_pct = (in_house / total_spaces * 100.0) if total_spaces else 0.0

        content = (
            'Night Audit Report — %s — %s\n\n'
            'Arrivals: %d\n'
            'Departures: %d\n'
            'No-Shows: %d\n'
            'In-House: %d / %d spaces (%.1f%% occupancy)\n'
            'Rooms Posted (this run): %d\n'
        ) % (
            self.property_id.display_name, self.business_date,
            arrivals, departures, no_shows,
            in_house, total_spaces, occupancy_pct,
            self.rooms_posted,
        )

        attachment = Attachment.create({
            'name': attachment_name,
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/plain',
        })
        self.variance_report_id = attachment.id

        return ('ok', 'Report bundle generated (%s).' % attachment.name)

    def _step_advance_business_date(self):
        """9. Write property.business_date = next_business_date.

        hospitality.property.write() restricts business_date changes
        to a custom check: `self.env.user.has_group(
        'hospitality_base.group_hospitality_admin')`. Note this checks
        env.user directly rather than env.su, so `.sudo()` alone does
        NOT bypass it — the acting user genuinely needs that group.
        This is surfaced as a clear 'failed' status rather than an
        opaque AccessError traceback, so whoever runs the audit knows
        exactly what to fix (grant the running user that group).

        Idempotent: checks the property's current business_date before
        writing, so re-running after a successful advance is a no-op.
        """
        self.ensure_one()

        if self.property_id.business_date == self.next_business_date:
            return (
                'ok',
                'Business date already advanced to %s.' % self.next_business_date,
            )

        if self.property_id.business_date != self.business_date:
            return (
                'failed',

                    "Property business date (%(prop_date)s) does not match "
                    "this audit run's business date (%(run_date)s) — "
                    "refusing to advance."
                 % {
                    'prop_date': self.property_id.business_date,
                    'run_date': self.business_date,
                },
            )

        try:
            self.property_id.sudo().write({
                'business_date': self.next_business_date,
            })
        except AccessError:
            return (
                'failed',
                    'Could not advance business date: the user running this '
                    'audit lacks the Hospitality Admin group required by '
                    'hospitality.property.write().'
            )

        return (
            'ok',
            'Business date advanced from %(old)s to %(new)s.' % {
                'old': self.business_date, 'new': self.next_business_date,
            },
        )

    def _step_lock_period(self):
        """10. If a fiscal lock date field is available (Enterprise),
        set it to business_date. No-op on Community.

        GAP: the spec names 'account.fiscal.lock' as a model, but no
        such model exists in stock Odoo Community or Enterprise as far
        as this implementation could determine — period locking is
        normally represented via lock-date fields directly on
        res.company (e.g. fiscalyear_lock_date), not a separate model.
        This defensively probes for known lock-date field names on the
        property's company and no-ops (status='skipped') if none are
        found, rather than referencing a model name that may not
        exist.
        """
        self.ensure_one()
        company = self.property_id.company_id

        lock_field = None
        for candidate in ('fiscalyear_lock_date', 'period_lock_date'):
            if candidate in company._fields:
                lock_field = candidate
                break

        if not lock_field:
            return ('skipped', 'Fiscal lock not available on this edition — no-op.')

        current = getattr(company, lock_field)
        if current and current >= self.business_date:
            return (
                'ok',
                'Fiscal lock date already at or past %s.' % self.business_date,
            )

        try:
            company.sudo().write({lock_field: self.business_date})
        except Exception as exc:
            detail = exc.args[0] if getattr(exc, 'args', None) else str(exc)
            if not isinstance(detail, str):
                detail = str(exc)
            return ('skipped', 'Could not set fiscal lock: %s' % detail)

        return ('ok', 'Fiscal lock date set to %s.' % self.business_date)

    def _step_reconcile_journal(self):
        """11. Compare the day's folio postings against the journal
        items raised for them and report any variance."""
        lines = self.env['hospitality.folio.line'].search([
            ('property_id', '=', self.property_id.id),
            ('business_date', '=', self.business_date),
            ('is_void', '=', False),
        ])
        operational = sum(lines.mapped('amount_total'))
        journalled = sum(
            lines.filtered('account_move_line_id')
            .mapped('account_move_line_id.balance')
        )
        variance = operational - journalled

        if self.currency_id.is_zero(variance):
            return ('ok', 'Folio and journal agree (%d lines).' % len(lines))

        return (
            'failed',
            'Variance of %s between folio postings and journal.'
            % self.currency_id.format(variance),
        )