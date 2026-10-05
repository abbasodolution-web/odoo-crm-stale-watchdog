from odoo import fields, models


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    stale_threshold_days = fields.Integer(
        string='Stale after (days)',
        help="Days without real activity before an opportunity in this stage is flagged as stale. "
             "Leave 0 to use the company setting.")
