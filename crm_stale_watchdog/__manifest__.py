{
    'name': 'Stale Opportunity Watchdog',
    'version': '17.0.1.0.1',
    'category': 'Sales/CRM',
    'summary': 'Auto-reminds salespeople about opportunities that have gone quiet',
    'description': """
Stale Opportunity Watchdog
===========================
Configure an inactivity threshold (in days). A daily scheduled action scans
open CRM opportunities that haven't been updated within that window and
automatically schedules a follow-up reminder activity for the assigned
salesperson - so nothing quietly falls through the cracks in your pipeline.

Also adds a "Stale" indicator to opportunities, filterable and groupable
right from the Pipeline search bar.

Features
--------
* Configurable inactivity threshold (Settings > CRM)
* Daily cron flags stale opportunities and creates a follow-up activity
  for the assigned salesperson
* Duplicate-safe: never creates a second pending reminder while one is
  already open on the same opportunity
* "Stale Opportunities" filter and "Stale" group-by in the Pipeline view
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
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
