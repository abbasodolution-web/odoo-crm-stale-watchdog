from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    crm_stale_threshold_days = fields.Integer(related='company_id.crm_stale_threshold_days', readonly=False)
    crm_stale_escalation_days = fields.Integer(related='company_id.crm_stale_escalation_days', readonly=False)
    crm_stale_ignore_tag_ids = fields.Many2many(related='company_id.crm_stale_ignore_tag_ids', readonly=False)
