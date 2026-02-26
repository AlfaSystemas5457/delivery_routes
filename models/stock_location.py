from odoo import models, fields


class StockLocation(models.Model):
    _inherit = "stock.location"

    def get_location_id(self):
        location_ids = []
        for rec in self:
            location_ids.append(rec.location_id.id)
        return location_ids
