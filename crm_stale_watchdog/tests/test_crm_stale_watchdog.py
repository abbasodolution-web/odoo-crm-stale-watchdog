from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCrmStaleWatchdog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(
            'crm_stale_watchdog.threshold_days', '1')
        self.salesperson = self.env.ref('base.user_admin')
        self.lead = self.env['crm.lead'].create({
            'name': 'Test Stale Opportunity',
            'type': 'opportunity',
            'user_id': self.salesperson.id,
        })

    def _backdate(self, days):
        self.env.cr.execute(
            "UPDATE crm_lead SET write_date = write_date - interval %s WHERE id = %s",
            (f'{days} days', self.lead.id),
        )
        self.lead.invalidate_recordset(['write_date'])

    def _activity_count(self):
        activity_type = self.env.ref(
            'crm_stale_watchdog.mail_act_stale_opportunity_reminder')
        return self.env['mail.activity'].search_count([
            ('res_model', '=', 'crm.lead'),
            ('res_id', '=', self.lead.id),
            ('activity_type_id', '=', activity_type.id),
        ])

    def test_stale_lead_gets_flagged_and_reminded(self):
        self._backdate(5)
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertTrue(self.lead.is_stale)
        self.assertEqual(self._activity_count(), 1)

    def test_no_duplicate_reminder_on_second_run(self):
        self._backdate(5)
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertEqual(self._activity_count(), 1)

    def test_is_stale_clears_when_won(self):
        self._backdate(5)
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertTrue(self.lead.is_stale)

        self.lead.stage_id = self.env.ref('crm.stage_lead4')  # Won
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertFalse(self.lead.is_stale)

    def test_stays_stale_on_next_run(self):
        self._backdate(5)
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertTrue(self.lead.is_stale)

    def test_flagging_does_not_count_as_update(self):
        self._backdate(5)
        before = self.lead.write_date
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.lead.invalidate_recordset(['write_date'])
        self.assertEqual(self.lead.write_date, before)

    def test_real_update_clears_stale(self):
        self._backdate(5)
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.lead.expected_revenue = 1000
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertFalse(self.lead.is_stale)

    def test_is_stale_clears_when_lost(self):
        self._backdate(5)
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.lead.action_set_lost()
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertFalse(self.lead.with_context(active_test=False).is_stale)

    def test_zero_threshold_does_not_flag_fresh_leads(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'crm_stale_watchdog.threshold_days', '0')
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.assertFalse(self.lead.is_stale)
