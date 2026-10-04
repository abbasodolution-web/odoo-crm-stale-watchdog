from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    crm_stale_watchdog_threshold_days = fields.Integer(
        string='Stale Opportunity Threshold (days)',
        default=30,
        config_parameter='crm_stale_watchdog.threshold_days',
        help="Number of days an opportunity can go without any update "
             "before the Stale Opportunity Watchdog flags it and reminds "
             "its salesperson.",
    )
