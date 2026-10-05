from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CrmStaleSnoozeWizard(models.TransientModel):
    _name = 'crm.stale.snooze.wizard'
    _description = 'Pause Stale Opportunity Reminders'

    lead_ids = fields.Many2many('crm.lead', string='Opportunities', required=True)
    period = fields.Selection([
        ('1w', '1 week'),
        ('2w', '2 weeks'),
        ('1m', '1 month'),
        ('3m', '3 months'),
        ('custom', 'Pick a date'),
    ], default='2w', required=True)
    snooze_until = fields.Date(string='Pause until', required=True,
                               default=lambda self: fields.Date.context_today(self) + relativedelta(weeks=2))
    reason = fields.Char(help="Shown in the chatter, e.g. 'Customer budget opens in January'.")

    @api.onchange('period')
    def _onchange_period(self):
        delta = {'1w': relativedelta(weeks=1), '2w': relativedelta(weeks=2),
                 '1m': relativedelta(months=1), '3m': relativedelta(months=3)}.get(self.period)
        if delta:
            self.snooze_until = fields.Date.context_today(self) + delta

    def action_snooze(self):
        self.ensure_one()
        if self.snooze_until <= fields.Date.context_today(self):
            raise UserError(_("Choose a date in the future."))
        self.lead_ids.write({'stale_snoozed_until': self.snooze_until})
        self.lead_ids._stale_remove_pending_activities()
        self.lead_ids.with_context(tracking_disable=True).write({'is_stale': False, 'stale_days': 0, 'stale_escalated': False})
        note = _("Stale reminders paused until %s.", fields.Date.to_string(self.snooze_until))
        if self.reason:
            note += ' ' + _("Reason: %s", self.reason)
        for lead in self.lead_ids:
            lead.message_post(body=note, subtype_xmlid='mail.mt_note')
        return {'type': 'ir.actions.act_window_close'}
