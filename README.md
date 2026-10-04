# Stale Opportunity Watchdog — Odoo 17 CRM

![Stale Opportunity Watchdog](crm_stale_watchdog/static/description/banner.png)

Never let a deal go quiet. Every day this module flags open CRM opportunities that
haven't been updated for a number of days you choose, and gives the assigned
salesperson a **Stale Opportunity Follow-up** activity.

## Features
- Configurable inactivity threshold (Settings › CRM, default 30 days)
- Daily scheduled action flags idle opportunities
- Follow-up activity for the salesperson, never duplicated while one is open
- Flag clears automatically when the opportunity is updated, won or lost
- "Stale Opportunities" filter and "Stale" group-by in the Pipeline
- Depends only on `crm` and `mail`; covered by automated tests

## Install
Copy `crm_stale_watchdog` into your addons path, update the Apps list, and install
**Stale Opportunity Watchdog**.

## Author
**ABBAS** — custom Odoo development (Odoo 17 & 19). Support: abbasodolution@gmail.com

License: LGPL-3
