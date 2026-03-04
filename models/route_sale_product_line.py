from odoo import models, fields, api


class RouteSaleProductLine(models.Model):
    _name = "route.sale.product.line"
    _description = "Línea de productos vendidos en dirección"

    sale_address_id = fields.Many2one(
        "route.sale.address", string="Dirección de Venta", ondelete="cascade"
    )

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('id', 'in', route_product_ids)]",
    )
    quantity = fields.Float(string="Cantidad", default=1.0)

    no_charge = fields.Boolean(string="Producto sin cargo", default=False)

    route_product_ids = fields.Many2many(
        "product.product",
        string="Productos de la Ruta",
        compute="_compute_route_products",
        store=True,
    )

    @api.depends("sale_address_id.route_id.product")
    def _compute_route_products(self):
        for rec in self:
            rec.route_product_ids = rec.sale_address_id.route_id.product.ids
