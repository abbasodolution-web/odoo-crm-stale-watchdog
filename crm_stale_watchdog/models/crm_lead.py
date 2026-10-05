from datetime import timedelta

from odoo import _, api, fields, models

REMINDER_XMLID = 'crm_stale_watchdog.mail_act_stale_opportunity_reminder'
ESCALATION_XMLID = 'crm_stale_watchdog.mail_act_stale_opportunity_escalation'
DEFAULT_THRESHOLD_DAYS = 30


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    is_stale = fields.Boolean(
        string='Stale', copy=False, index=True, readonly=True,
        help="No real activity (a note, an email, a completed activity or a stage change) for longer "
             "than the stale threshold. Set by the daily Stale Opportunity Watchdog run, and cleared "
             "as soon as someone works on the opportunity.")
    stale_days = fields.Integer(
        string='Days Inactive', copy=False, readonly=True, aggregator='avg',
        help="Days since the last real activity, as of the last Watchdog run.")
    stale_last_touch_date = fields.Datetime(
        string='Last Real Activity', copy=False, readonly=True,
        help="Last note, email, completed activity or stage change on this opportunity.")
    stale_snoozed_until = fields.Date(
        string='Stale Reminders Paused Until', copy=False, tracking=True,
        help="The Watchdog leaves this opportunity alone until this date.")
    stale_escalated = fields.Boolean(copy=False, readonly=True)

    # ------------------------------------------------------------------
    # Clearing in real time
    # ------------------------------------------------------------------

    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals:
            # A stage change is real activity
            self.filtered('is_stale')._stale_clear()
        return res

    def _message_post_after_hook(self, message, msg_vals):
        res = super()._message_post_after_hook(message, msg_vals)
        if self.is_stale and self._stale_is_touch(message):
            self._stale_clear()
        return res

    def _stale_is_touch(self, message):
        """A note, an email or a completed activity written by a person."""
        if message.author_id == self.env.ref('base.partner_root'):
            return False
        return message.message_type in ('comment', 'email') or bool(message.mail_activity_type_id)

    def _stale_clear(self):
        # The pending reminder is removed by the next run (or completed by the
        # user), never here: this runs while an activity is being marked done.
        self.sudo().with_context(tracking_disable=True).write({
            'is_stale': False,
            'stale_days': 0,
            'stale_escalated': False,
            'stale_last_touch_date': fields.Datetime.now(),
        })

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_open_stale_snooze(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pause Stale Reminders'),
            'res_model': 'crm.stale.snooze.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_ids': self.ids},
        }

    def action_stale_unsnooze(self):
        self.write({'stale_snoozed_until': False})

    # ------------------------------------------------------------------
    # Daily run
    # ------------------------------------------------------------------

    @api.model
    def _stale_open_domain(self):
        return [
            ('type', '=', 'opportunity'),
            ('active', '=', True),
            '|', ('stage_id', '=', False), ('stage_id.is_won', '=', False),
        ]

    def _stale_last_touch_dates(self):
        """Last real activity per lead, in one query: the latest of creation,
        stage change and any note, email or completed activity by a person."""
        if not self:
            return {}
        self.env['mail.message'].flush_model()
        self.flush_model(['create_date', 'date_last_stage_update'])
        self.env.cr.execute("""
            SELECT l.id, GREATEST(l.create_date, l.date_last_stage_update, MAX(m.date))
              FROM crm_lead l
         LEFT JOIN mail_message m
                ON m.model = 'crm.lead' AND m.res_id = l.id
               AND (m.message_type IN ('comment', 'email') OR m.mail_activity_type_id IS NOT NULL)
               AND m.author_id IS DISTINCT FROM %s
             WHERE l.id IN %s
          GROUP BY l.id
        """, [self.env.ref('base.partner_root').id, tuple(self.ids)])
        return dict(self.env.cr.fetchall())

    def _stale_threshold(self, company):
        stage_days = self.stage_id.stale_threshold_days
        return max(1, stage_days or company.crm_stale_threshold_days or DEFAULT_THRESHOLD_DAYS)

    @api.model
    def _cron_check_stale_opportunities(self):
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        leads = self.search(self._stale_open_domain())
        touches = leads._stale_last_touch_dates()

        stale, fresh = self.browse(), self.browse()
        updates = {}
        for lead in leads:
            company = lead.company_id or self.env.company
            touch = touches.get(lead.id) or lead.create_date
            days = max(0, (now - touch).days)
            ignored = bool(lead.tag_ids & company.crm_stale_ignore_tag_ids)
            snoozed = lead.stale_snoozed_until and lead.stale_snoozed_until > today
            if days >= lead._stale_threshold(company) and not ignored and not snoozed:
                stale |= lead
                updates.setdefault((True, days, touch), []).append(lead.id)
            else:
                fresh |= lead
                updates.setdefault((False, 0, touch), []).append(lead.id)
        for (is_stale, days, touch), ids in updates.items():
            vals = {'is_stale': is_stale, 'stale_days': days, 'stale_last_touch_date': touch}
            if not is_stale:
                vals['stale_escalated'] = False
            self.browse(ids).with_context(tracking_disable=True).write(vals)

        # Won, lost, archived or turned back into a lead: no longer watched
        gone = self.with_context(active_test=False).search([('is_stale', '=', True), ('id', 'not in', leads.ids)])
        gone.with_context(tracking_disable=True).write({'is_stale': False, 'stale_days': 0, 'stale_escalated': False})
        (fresh | gone)._stale_remove_pending_activities()

        stale._stale_schedule_reminders()
        stale._stale_escalate(today)

    def _stale_remove_pending_activities(self):
        types = self.env.ref(REMINDER_XMLID) | self.env.ref(ESCALATION_XMLID)
        self.env['mail.activity'].search([
            ('res_model', '=', 'crm.lead'), ('res_id', 'in', self.ids),
            ('activity_type_id', 'in', types.ids),
        ]).unlink()

    def _stale_responsible(self):
        """The salesperson, or the team leader when there is none."""
        return self.user_id or self.team_id.user_id

    def _stale_schedule_reminders(self):
        reminder = self.env.ref(REMINDER_XMLID)
        for lead in self:
            responsible = lead._stale_responsible()
            if not responsible or reminder in lead.activity_ids.activity_type_id:
                continue
            lead.activity_schedule(
                REMINDER_XMLID,
                summary=_("Follow up: no activity for %s days", lead.stale_days),
                note=_("Nobody has logged a note, sent an email or completed an activity on this "
                       "opportunity for %(days)s days. Follow up, or pause the reminders if it is waiting on purpose.",
                       days=lead.stale_days),
                user_id=responsible.id,
            )

    def _stale_escalate(self, today):
        reminder = self.env.ref(REMINDER_XMLID)
        for lead in self.filtered(lambda l: not l.stale_escalated and l.team_id.user_id):
            company = lead.company_id or self.env.company
            if company.crm_stale_escalation_days <= 0:
                continue
            overdue = lead.activity_ids.filtered(
                lambda a: a.activity_type_id == reminder
                and a.date_deadline <= today - timedelta(days=company.crm_stale_escalation_days))
            leader = lead.team_id.user_id
            if not overdue or overdue.user_id == leader:
                continue
            lead.activity_schedule(
                ESCALATION_XMLID,
                summary=_("Escalated: stale for %s days", lead.stale_days),
                note=_("The follow-up reminder for %(user)s has been overdue for more than %(days)s days.",
                       user=overdue[0].user_id.name, days=company.crm_stale_escalation_days),
                user_id=leader.id,
            )
            lead.with_context(tracking_disable=True).write({'stale_escalated': True})
