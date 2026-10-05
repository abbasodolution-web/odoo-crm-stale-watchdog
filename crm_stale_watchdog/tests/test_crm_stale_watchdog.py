from datetime import timedelta

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged

REMINDER = 'crm_stale_watchdog.mail_act_stale_opportunity_reminder'
ESCALATION = 'crm_stale_watchdog.mail_act_stale_opportunity_escalation'


@tagged('post_install', '-at_install')
class TestCrmStaleWatchdog(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'crm_stale_threshold_days': 10, 'crm_stale_escalation_days': 3,
                           'crm_stale_ignore_tag_ids': [(5, 0, 0)]})
        cls.salesperson = cls.env['res.users'].create({
            'name': 'Sara Sales', 'login': 'sara.stale', 'email': 'sara@example.com',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])]})
        cls.leader = cls.env['res.users'].create({
            'name': 'Liam Leader', 'login': 'liam.stale', 'email': 'liam@example.com',
            'groups_id': [(6, 0, [cls.env.ref('sales_team.group_sale_manager').id])]})
        cls.team = cls.env['crm.team'].create({'name': 'Stale Team', 'user_id': cls.leader.id})
        cls.stage_new = cls.env['crm.stage'].create({'name': 'Stale New', 'sequence': 1})
        cls.stage_quick = cls.env['crm.stage'].create({'name': 'Stale Quick', 'sequence': 2,
                                                       'stale_threshold_days': 3})
        cls.stage_won = cls.env['crm.stage'].create({'name': 'Stale Won', 'sequence': 3, 'is_won': True})

    def setUp(self):
        super().setUp()
        self.lead = self._lead('Quiet deal')

    def _lead(self, name, **vals):
        return self.env['crm.lead'].create(dict({
            'name': name, 'type': 'opportunity', 'user_id': self.salesperson.id,
            'team_id': self.team.id, 'stage_id': self.stage_new.id}, **vals))

    def _age(self, lead, days):
        """Make every trace of activity on the lead `days` old."""
        self.env.flush_all()
        self.env.cr.execute("""
            UPDATE crm_lead SET create_date = create_date - %(d)s, date_last_stage_update = date_last_stage_update - %(d)s
             WHERE id = %(id)s;
            UPDATE mail_message SET date = date - %(d)s WHERE model = 'crm.lead' AND res_id = %(id)s;
        """, {'d': timedelta(days=days), 'id': lead.id})
        self.env.invalidate_all()

    def _run(self):
        self.env['crm.lead']._cron_check_stale_opportunities()
        self.env.invalidate_all()

    def _activities(self, lead, xmlid):
        return lead.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref(xmlid))

    def test_quiet_opportunity_is_flagged_and_reminded(self):
        self._age(self.lead, 12)
        self._run()
        self.assertTrue(self.lead.is_stale)
        self.assertEqual(self.lead.stale_days, 12)
        reminder = self._activities(self.lead, REMINDER)
        self.assertEqual(len(reminder), 1)
        self.assertEqual(reminder.user_id, self.salesperson)

    def test_recent_opportunity_is_not_flagged(self):
        self._age(self.lead, 5)
        self._run()
        self.assertFalse(self.lead.is_stale)
        self.assertFalse(self._activities(self.lead, REMINDER))

    def test_no_duplicate_reminder(self):
        self._age(self.lead, 12)
        self._run()
        self._run()
        self.assertEqual(len(self._activities(self.lead, REMINDER)), 1)

    def test_automatic_writes_do_not_count_as_activity(self):
        self._age(self.lead, 12)
        self.lead.with_context(tracking_disable=True).write({'expected_revenue': 5000})
        self._run()
        self.assertTrue(self.lead.is_stale)

    def test_note_clears_immediately_and_reminder_is_removed(self):
        self._age(self.lead, 12)
        self._run()
        self.lead.with_user(self.salesperson).message_post(body='Called the customer', message_type='comment',
                                                           subtype_xmlid='mail.mt_note')
        self.assertFalse(self.lead.is_stale)
        self._run()
        self.assertFalse(self.lead.is_stale)
        self.assertFalse(self._activities(self.lead, REMINDER))

    def test_marking_the_reminder_done_clears_stale(self):
        self._age(self.lead, 12)
        self._run()
        self._activities(self.lead, REMINDER).with_user(self.salesperson).action_feedback(feedback='Followed up')
        self.assertFalse(self.lead.is_stale)
        self._run()
        self.assertFalse(self.lead.is_stale)

    def test_bot_messages_do_not_count(self):
        self._age(self.lead, 12)
        self.lead.with_user(self.env.ref('base.user_root')).message_post(
            body='Automatic message', message_type='comment', author_id=self.env.ref('base.partner_root').id)
        self._run()
        self.assertTrue(self.lead.is_stale)

    def test_stage_limit_overrides_company(self):
        quick = self._lead('Quick stage deal', stage_id=self.stage_quick.id)
        self._age(quick, 4)
        self._age(self.lead, 4)
        self._run()
        self.assertTrue(quick.is_stale)
        self.assertFalse(self.lead.is_stale)

    def test_stage_change_clears_stale(self):
        self._age(self.lead, 12)
        self._run()
        self.lead.stage_id = self.stage_quick
        self.assertFalse(self.lead.is_stale)
        self._run()
        self.assertFalse(self.lead.is_stale)

    def test_won_and_lost_are_unflagged(self):
        lost = self._lead('Lost deal')
        self._age(self.lead, 12)
        self._age(lost, 12)
        self._run()
        self.env.flush_all()
        self.env.cr.execute("UPDATE crm_lead SET stage_id = %s WHERE id = %s", [self.stage_won.id, self.lead.id])
        lost.action_set_lost()
        self.env.invalidate_all()
        self._run()
        self.assertFalse(self.lead.is_stale)
        self.assertFalse(lost.with_context(active_test=False).is_stale)
        self.assertFalse(self._activities(self.lead, REMINDER))

    def test_ignored_tag(self):
        tag = self.env['crm.tag'].create({'name': 'Long cycle'})
        self.company.crm_stale_ignore_tag_ids = tag
        self.lead.tag_ids = tag
        self._age(self.lead, 40)
        self._run()
        self.assertFalse(self.lead.is_stale)

    def test_snooze_and_wake_up(self):
        self._age(self.lead, 12)
        self._run()
        wizard = Form(self.env['crm.stale.snooze.wizard'].with_context(default_lead_ids=self.lead.ids))
        wizard.period = '1w'
        wizard.reason = 'Budget in January'
        wizard.save().action_snooze()
        self.assertFalse(self.lead.is_stale)
        self.assertFalse(self._activities(self.lead, REMINDER))
        self.assertIn('Budget in January', self.lead.message_ids[0].body)
        self._age(self.lead, 12)
        self._run()
        self.assertFalse(self.lead.is_stale, "Still snoozed")
        self.lead.stale_snoozed_until = fields.Date.today() - timedelta(days=1)
        self._run()
        self.assertTrue(self.lead.is_stale, "Snooze is over")

    def test_escalation_to_team_leader_once(self):
        self._age(self.lead, 12)
        self._run()
        self.assertFalse(self._activities(self.lead, ESCALATION))
        self._activities(self.lead, REMINDER).date_deadline = fields.Date.today() - timedelta(days=4)
        self._run()
        self._run()
        escalation = self._activities(self.lead, ESCALATION)
        self.assertEqual(len(escalation), 1)
        self.assertEqual(escalation.user_id, self.leader)

    def test_escalation_off(self):
        self.company.crm_stale_escalation_days = 0
        self._age(self.lead, 12)
        self._run()
        self._activities(self.lead, REMINDER).date_deadline = fields.Date.today() - timedelta(days=30)
        self._run()
        self.assertFalse(self._activities(self.lead, ESCALATION))

    def test_no_salesperson_goes_to_team_leader(self):
        orphan = self._lead('No owner', user_id=False)
        self._age(orphan, 12)
        self._run()
        self.assertEqual(self._activities(orphan, REMINDER).user_id, self.leader)
