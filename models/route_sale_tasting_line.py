from odoo import models, fields, api


class RouteSaleTastingLine(models.Model):
    _name = "route.sale.tasting.line"
    _description = "Línea de productos para degustación"

    sale_address_id = fields.Many2one(
        "route.sale.address",
        string="Dirección de venta",
        ondelete="cascade",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Producto para degustación",
        required=True,
        domain="[('id', 'in', route_product_ids)]",
    )
    quantity = fields.Float(
        string="Cantidad para degustación",
        required=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de medida",
        required=True,
        related="product_id.uom_id",
        readonly=True,
    )

    lot_id = fields.Many2one("stock.lot", string="Lote")
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
