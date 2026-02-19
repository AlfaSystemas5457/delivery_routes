from odoo import models, fields, api


class Address(models.Model):
    _name = "route.address"
    _description = "Dirección de visita"
    _inherit = ["mail.thread"]

    name = fields.Char(string="Nombre de la Ruta", required=True, tracking=True)
    description = fields.Text(string="Descripción", tracking=True)
    salesperson_ids = fields.Many2many(
        "res.users",
        string="Repartidores",
        required=True,
        tracking=True,
    )
    product = fields.Many2many(
        "product.product", string="Productos", required=True, tracking=True
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacenes",
        ondelete="cascade",
        required=True,
        tracking=True,
    )
    route_address_ids = fields.Many2many(
        "res.partner",
        relation="route_address_partner_rel",
        string="Direcciones",
        required=True,
        tracking=True,
        domain="[('user_id', 'in', salesperson_ids)]",
    )
    dates = fields.Many2many(
        "res.days",
        string="Día",
        required=True,
        tracking=True,
    )

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        partner = self.env.user

        employee = self.env["res.users"].search([("id", "=", partner.id)], limit=1)

        if employee:
            res["salesperson_ids"] = [(6, 0, [employee.id])]

        return res
