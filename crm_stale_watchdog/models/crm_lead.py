from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

STALE_ACTIVITY_XMLID = 'crm_stale_watchdog.mail_act_stale_opportunity_reminder'
DEFAULT_THRESHOLD_DAYS = 30


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    is_stale = fields.Boolean(
        string='Stale',
        default=False,
        copy=False,
        help="Set by the Stale Opportunity Watchdog when this opportunity "
             "hasn't been updated in longer than the configured threshold. "
             "Refreshed by the scheduled action, not in real time.",
    )

    def _get_stale_watchdog_threshold_days(self):
        # A threshold below one day would flag opportunities updated today.
        return max(1, int(self.env['ir.config_parameter'].sudo().get_param(
            'crm_stale_watchdog.threshold_days', default=DEFAULT_THRESHOLD_DAYS)))

    def _stale_watchdog_set_flag(self, value):
        """ Set is_stale without touching write_date. The flag is bookkeeping,
        not a user update; an ORM write would bump write_date and make the next
        run treat the opportunity as freshly updated and unflag it. """
        if not self:
            return
        self.flush_model(['is_stale'])
        self.env.cr.execute(
            "UPDATE crm_lead SET is_stale = %s WHERE id IN %s",
            (value, tuple(self.ids)),
        )
        self.invalidate_recordset(['is_stale'])

    @api.model
    def _stale_watchdog_open_opportunity_domain(self):
        """ Same 'still open' pattern used across crm core (won/lost aware). """
        return [
            ('type', '=', 'opportunity'),
            ('active', '=', True),
            '|', ('stage_id', '=', False), ('stage_id.is_won', '=', False),
        ]

    @api.model
    def _cron_check_stale_opportunities(self):
        threshold_days = self._get_stale_watchdog_threshold_days()
        limit_date = fields.Datetime.now() - relativedelta(days=threshold_days)
        open_domain = self._stale_watchdog_open_opportunity_domain()

        # Leads that ARE currently stale.
        stale_leads = self.search(open_domain + [
            ('user_id', '!=', False),
            ('write_date', '<=', limit_date),
        ])
        # Leads previously flagged that no longer qualify (updated, won,
        # lost, converted back to lead, etc.) -> unflag them. Lost
        # opportunities are archived, so include inactive records.
        no_longer_stale = self.with_context(active_test=False).search([
            ('is_stale', '=', True),
            ('id', 'not in', stale_leads.ids),
        ])
        no_longer_stale._stale_watchdog_set_flag(False)

        if not stale_leads:
            return

        stale_leads._stale_watchdog_set_flag(True)

        reminder_activity_type = self.env.ref(STALE_ACTIVITY_XMLID, raise_if_not_found=False)
        if not reminder_activity_type:
            return

        # Avoid re-nagging: skip leads that already carry a pending
        # activity of our dedicated type.
        leads_to_notify = stale_leads.filtered(
            lambda lead: reminder_activity_type not in lead.activity_ids.activity_type_id
        )

        for lead in leads_to_notify:
            lead.activity_schedule(
                STALE_ACTIVITY_XMLID,
                summary=_("Stale Opportunity Follow-up"),
                note=_(
                    "This opportunity hasn't been updated in over %(days)s days. "
                    "Please review and follow up.", days=threshold_days),
                user_id=lead.user_id.id,
            )
