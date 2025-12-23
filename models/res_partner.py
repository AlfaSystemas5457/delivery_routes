from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = "res.partner"

    def open_map(self):
        self.ensure_one()
        lat = self.partner_latitude or 0
        lng = self.partner_longitude or 0

        if lat == 0 or lng == 0:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": "No hay coordenadas disponibles para esta dirección.",
                    "type": "danger",
                },
            }

        url = f"https://www.google.com/maps?q={lat},{lng}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }
