from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    crm_stale_threshold_days = fields.Integer(
        string='Stale after (days)', default=30,
        help="An open opportunity with no real activity for this many days is flagged as stale. "
             "A stage can set its own number of days.")
    crm_stale_escalation_days = fields.Integer(
        string='Escalate after (days)', default=7,
        help="When the follow-up reminder is still not done this many days after its due date, "
             "the sales team leader gets an activity too. 0 turns escalation off.")
    crm_stale_ignore_tag_ids = fields.Many2many(
        'crm.tag', 'crm_stale_ignore_tag_rel', 'company_id', 'tag_id', string='Ignore tags',
        help="Opportunities with any of these tags are never flagged as stale.")
