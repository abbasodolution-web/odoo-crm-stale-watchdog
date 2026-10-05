{
    'name': 'Stale Opportunity Watchdog',
    'version': '18.0.2.0.0',
    'category': 'Sales/CRM',
    'summary': 'Find CRM opportunities that went quiet: reminders, per-stage limits, '
               'pause, escalation and a revenue-at-risk report',
    'description': """
Stale Opportunity Watchdog
==========================
Every day the Watchdog checks open opportunities for real activity: a note, an
email, a completed activity or a stage change. When there has been none for
longer than the limit, it flags the opportunity, shows a "Stale" badge in the
pipeline and gives the salesperson a follow-up reminder.

* Real activity, not "last modified": automatic updates don't hide a quiet deal
* A different limit per stage (e.g. 7 days in Proposition, 30 in New)
* Clears itself the moment someone logs a note, sends an email or moves the stage
* Pause the reminders on an opportunity until a date, with a reason in the chatter
* Escalates to the sales team leader when the reminder stays overdue
* No salesperson? The team leader gets the reminder
* Ignore opportunities with chosen tags
* "Stale Opportunities" report: revenue at risk per salesperson and stage
* Settings per company
""",
    'author': 'ABBAS',
    'maintainer': 'ABBAS',
    'support': 'abbasodolution@gmail.com',
    'license': 'LGPL-3',
    'depends': ['crm', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_activity_type_data.xml',
        'data/ir_cron_data.xml',
        'views/crm_lead_views.xml',
        'views/crm_stage_views.xml',
        'views/res_config_settings_views.xml',
        'views/crm_stale_snooze_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}
