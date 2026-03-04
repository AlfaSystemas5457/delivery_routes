from odoo import models, fields, api


class RouteSaleReturnLine(models.Model):
    _name = "route.sale.return.line"
    _description = "Línea de productos a devolver"

    sale_address_id = fields.Many2one(
        "route.sale.address",
        string="Dirección de venta",
        ondelete="cascade",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Producto a devolver",
        required=True,
        domain="[('id', 'in', route_product_ids)]",
    )
    quantity = fields.Float(
        string="Cantidad a devolver",
        compute="_compute_quantity",
    )

    move_line = fields.One2many(
        "route.sale.return.move.line",
        "return_line_id",
        string="Movimiento a devolcer",
    )
    lot_ids = fields.Many2many(
        "stock.lot",
        string="Lotes",
        compute="_compute_lot_ids",
        store=True,
    )

    route_product_ids = fields.Many2many(
        "product.product",
        string="Productos de la Ruta",
        compute="_compute_route_products",
        store=True,
    )

    has_stock_move = fields.Boolean(
        string="Tiene movimiento de inventario",
        compute="_compute_has_stock_move",
        store=True,
    )

    def action_show_details(self):
        self.ensure_one()
        return {
            "name": "Detalle de Lotes",
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "route.sale.return.line",
            "res_id": self.id,
            "target": "new",
        }

    @api.depends("lot_ids")
    def _compute_has_stock_move(self):
        for rec in self:
            rec.write({"has_stock_move": rec.sale_address_id.is_refunded})

    @api.depends("move_line.lot_id")
    def _compute_lot_ids(self):
        for rec in self:
            rec.lot_ids = rec.move_line.mapped("lot_id")

    @api.depends("move_line.quantity")
    def _compute_quantity(self):
        for rec in self:
            rec.quantity = sum(rec.move_line.mapped("quantity"))

    @api.depends("sale_address_id.route_id.product")
    def _compute_route_products(self):
        for rec in self:
            rec.route_product_ids = rec.sale_address_id.route_id.product.ids


class RouteSaleReturnMoveLine(models.Model):
    _name = "route.sale.return.move.line"
    _description = "Lineas de movimientos de productos"
    _rec_name = "lot_id"

    return_line_id = fields.Many2one(
        "route.sale.return.line", string="ID linea de devolución"
    )
    product_id = fields.Many2one(
        "product.product",
        related="return_line_id.product_id",
        store=True,
        readonly=True,
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote para degustación",
        domain="[('product_id', '=', product_id)]",
    )
    quantity = fields.Integer(string="Cantidad para degustación")
