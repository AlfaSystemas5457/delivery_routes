from odoo import models, fields, api, exceptions
import base64


class RouteSaleAddress(models.Model):
    _name = "route.sale.address"
    _description = "Dirección en Venta"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    address = fields.Char(string="Dirección")
    contact = fields.Many2one("res.partner", string="Contacto", ondelete="cascade")
    route_id = fields.Many2one(
        "route.route", string="Ruta", ondelete="cascade", index=True
    )
    product_lines = fields.One2many(
        "route.sale.product.line", "sale_address_id", string="Productos vendidos"
    )
    sale_order_id = fields.Many2one(
        "sale.order", string="Cotización Generada", readonly=True
    )
    status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("skipped", "Visitado sin pedido"),
            ("visited", "Visitado con pedido"),
        ],
        string="Estado de la visita",
        default="pending",
        required=True,
    )
    state = fields.Selection(
        [
            ("start", "Sin empezar"),
            ("process", "En proceso"),
            ("end", "Finalizado"),
        ],
        string="Estado de la Ruta",
        compute="_compute_state",
    )

    refund_id = fields.Many2one(
        "stock.picking", string="Movimiento de devolución", readonly=True
    )
    is_refund = fields.Boolean(string="Hay devolución?", default=False)
    is_refunded = fields.Boolean(string="Devuelto?", default=False)
    return_lines = fields.One2many(
        "route.sale.return.line", "sale_address_id", string="Productos a devolver"
    )

    tasting_id = fields.Many2one(
        "stock.picking", string="Movimiento de degustación", readonly=True
    )
    is_tasting = fields.Boolean(string="Hay degustación?", default=False)
    is_tasted = fields.Boolean(string="Degustado?", default=False)
    tasting_lines = fields.One2many(
        "route.sale.tasting.line", "sale_address_id", string="Productos a devolver"
    )

    ticket_pdf = fields.Binary(string="Ticket PDF", readonly=True)
    current_step = fields.Integer(default=0)

    delivery_time = fields.Datetime(string="Hora de la entrega")
    refund_time = fields.Datetime(string="Hora de la devolución")
    tasting_time = fields.Datetime(string="Hora de la entrega de la degustación")

    def _compute_state(self):
        for rec in self:
            rec.state = rec.route_id.state

    def _validations(self):
        if not self.contact:
            raise exceptions.UserError("Debes seleccionar un contacto.")

        if not self.route_id.warehouse_id:
            raise exceptions.UserError("La ruta no tiene asignado un almacén.")

        if (
            not self.product_lines
            or sum(line.quantity for line in self.product_lines) <= 0
        ):
            raise exceptions.UserError("No se asignaron productos.")

    def _validations_refund(self):
        if not self.contact:
            raise exceptions.UserError("Debes seleccionar un contacto.")

        if not self.route_id.warehouse_id:
            raise exceptions.UserError("La ruta no tiene asignado un almacén.")

        if (
            not self.return_lines
            or sum(line.quantity for line in self.return_lines) <= 0
        ):
            raise exceptions.UserError("No se asignaron productos.")

    def _validations_tasting(self):
        if not self.contact:
            raise exceptions.UserError("Debes seleccionar un contacto.")

        if not self.route_id.warehouse_id:
            raise exceptions.UserError("La ruta no tiene asignado un almacén.")

        if (
            not self.tasting_lines
            or sum(line.quantity for line in self.tasting_lines) <= 0
        ):
            raise exceptions.UserError("No se asignaron productos.")

    # def action_load_route_products(self):
    #     for record in self:
    #         if record.route_id and not record.product_lines:
    #             product_lines = []
    #             for product in record.route_id.product:
    #                 product_lines.append(
    #                     (0, 0, {"product_id": product.id, "quantity": 0.0})
    #                 )
    #             record.product_lines = product_lines

    def create_return_picking(self):
        self.ensure_one()
        self._validations_refund()

        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        MoveLine = self.env["stock.move.line"]

        return_picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("warehouse_id", "=", self.route_id.warehouse_id.id),
            ],
            limit=1,
        )
        if not return_picking_type:
            raise exceptions.UserError(
                "No se encontró tipo de operación para devoluciones."
            )

        customer_loc = self.env["stock.location"].search(
            [("usage", "=", "customer")], limit=1
        )
        if not customer_loc:
            raise exceptions.UserError(
                "Debes crear una ubicación de tipo Cliente (Customer) en Inventario."
            )

        warehouse_loc = self.route_id.warehouse_id.lot_stock_id

        picking = Picking.create(
            {
                "partner_id": self.contact.id,
                "picking_type_id": return_picking_type.id,
                "location_id": customer_loc.id,
                "location_dest_id": warehouse_loc.id,
                "origin": f"Devolución Ruta {self.route_id.name}",
            }
        )

        for line in self.return_lines:
            if line.quantity <= 0:
                continue

            move = Move.create(
                {
                    "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "product_uom": line.product_id.uom_id.id,
                    "product_uom_qty": 0,
                }
            )

            MoveLine.create(
                {
                    "move_id": move.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_id.uom_id.id,
                    "lot_id": line.lot_id.id,
                    "quantity": line.quantity,
                }
            )

        picking.action_confirm()
        picking.button_validate()

        self.write(
            {
                "is_refunded": True,
                "refund_id": picking.id,
                "refund_time": fields.Datetime.now(),
            }
        )

        return picking

    def create_tasting_picking(self, signature=False):
        self.ensure_one()
        self._validations_tasting()

        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        MoveLine = self.env["stock.move.line"]

        return_picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id", "=", self.route_id.warehouse_id.id),
            ],
            limit=1,
        )
        if not return_picking_type:
            raise exceptions.UserError(
                "No se encontró tipo de operación para devoluciones."
            )

        customer_loc = self.env["stock.location"].search(
            [("usage", "=", "customer")], limit=1
        )
        if not customer_loc:
            raise exceptions.UserError(
                "Debes crear una ubicación de tipo Cliente (Customer) en Inventario."
            )

        warehouse_loc = self.route_id.warehouse_id.lot_stock_id

        picking = Picking.create(
            {
                "partner_id": self.contact.id,
                "picking_type_id": return_picking_type.id,
                "location_id": warehouse_loc.id,
                "location_dest_id": customer_loc.id,
                "origin": f"Degustación Ruta {self.route_id.name}",
                "customer_signature": signature if signature else False,
            }
        )

        for line in self.tasting_lines:
            if line.quantity <= 0:
                continue

            move = Move.create(
                {
                    "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "product_uom": line.product_id.uom_id.id,
                    "product_uom_qty": 0,
                }
            )

            MoveLine.create(
                {
                    "move_id": move.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_id.uom_id.id,
                    "lot_id": line.lot_id.id,
                    "quantity": line.quantity,
                }
            )

        picking.action_confirm()

        self.write(
            {
                "is_tasted": True,
                "tasting_id": picking.id,
                "tasting_time": fields.Datetime.now(),
            }
        )

        if signature:
            picking.button_validate()
            return picking.id

        return {
            "type": "ir.actions.act_window",
            "name": "Movimiento de degustación",
            "res_model": "stock.picking",
            "res_id": self.tasting_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def handle_button_ticket(self):
        self.ensure_one()
        self.generate_ticket()
        return self.env.ref(
            "delivery_routes.action_report_route_sale_address"
        ).report_action(self)

    def generate_ticket(self):
        self.ensure_one()

        self._validations()

        report_name = "delivery_routes.action_report_route_sale_address"
        report_obj = self.env.ref(report_name)

        pdf_content, content_type = self.env["ir.actions.report"]._render_qweb_pdf(
            report_obj.report_name, [self.id]
        )

        self.ticket_pdf = base64.b64encode(pdf_content).decode("utf-8")

    def get_ticket_pos(self):
        self.ensure_one()
        self.generate_ticket()

        return {
            "ticket_pdf": self.ticket_pdf,
            "filename": f"ticket_{self.id}.pdf",
        }

    def handle_button_sale(self):
        self.ensure_one()

        for record in self:
            order = self.env["sale.order"].create(
                {
                    "partner_id": record.contact.id,
                    "origin": "Ruta: %s" % (record.route_id.name or ""),
                    "warehouse_id": record.route_id.warehouse_id.id,
                    "user_id": self.env.user.id,
                    "preferred_payment_method_line_id": self.contact.property_inbound_payment_method_line_id.id
                    or False,
                }
            )

            for line in record.product_lines:
                if line.quantity > 0:
                    self.env["sale.order.line"].create(
                        {
                            "order_id": order.id,
                            "product_id": line.product_id.id,
                            "product_uom_qty": line.quantity,
                            "price_unit": line.product_id.lst_price,
                            "name": line.product_id.name,
                        }
                    )

            self.write(
                {
                    "sale_order_id": order,
                    "status": "visited",
                    "delivery_time": fields.Datetime.now(),
                }
            )
            record.generate_ticket()
            return {
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "res_id": order.id,
                "view_mode": "form",
                "target": "current",
            }

    def handle_cancel(self):
        return {"type": "ir.actions.act_window_close"}

    def handle_skipped(self):
        self.status = "skipped"
        return {"type": "ir.actions.act_window_close"}

    def _compute_address_from_contact(self, contact):
        return " ".join(
            filter(
                None,
                [
                    contact.street,
                    contact.street2,
                    contact.city,
                    contact.state_id.name,
                    contact.zip,
                ],
            )
        )

    @api.onchange("contact")
    def _onchange_contact(self):
        if self.contact:
            self.address = self._compute_address_from_contact(self.contact)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("contact") and not vals.get("address"):
                contact = self.env["res.partner"].browse(vals["contact"])
                vals["address"] = self._compute_address_from_contact(contact)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("contact") and not vals.get("address"):
            contact = self.env["res.partner"].browse(vals["contact"])
            vals["address"] = self._compute_address_from_contact(contact)
        return super().write(vals)

    def open_map(self):
        self.ensure_one()
        lat = self.contact.partner_latitude or 0
        lng = self.contact.partner_longitude or 0

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

    def action_save_product_quantities(self, lines):
        self.ensure_one()

        for line in lines:
            product_line = self.env["route.sale.product.line"].browse(line["id"])
            if product_line.sale_address_id.id != self.id:
                continue

            product_line.quantity = line["quantity"]

        return True

    def action_save_product_quantities_refund(self, lines):
        self.ensure_one()

        for line in lines:
            product_line = self.env["route.sale.return.line"].browse(line["id"])
            if product_line.sale_address_id.id != self.id:
                continue

            product_line.quantity = line["quantity"]

        return True

    def action_save_product_quantities_tasting(self, lines):
        self.ensure_one()

        for line in lines:
            product_line = self.env["route.sale.tasting.line"].browse(line["id"])
            if product_line.sale_address_id.id != self.id:
                continue

            product_line.quantity = line["quantity"]

        return True

    def action_load_route_products(self):
        self.ensure_one()

        if not self.route_id:
            raise exceptions.UserError("La dirección no tiene ruta asignada.")

        if not self.product_lines:
            self.product_lines = [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": 0.0,
                    },
                )
                for product in self.route_id.product
            ]

        if not self.return_lines:
            self.return_lines = [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": 0.0,
                    },
                )
                for product in self.route_id.product
            ]

        if not self.tasting_lines:
            self.tasting_lines = [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": 0.0,
                    },
                )
                for product in self.route_id.product
            ]

        return {
            "id": self.id,
            "contact": self.contact.id if self.contact else False,
            "address": self.address,
            "status": self.status,
            "product_lines": self.product_lines.read(
                [
                    "id",
                    "product_id",
                    "quantity",
                ]
            ),
            "sale_order_id": self.sale_order_id.id if self.sale_order_id else False,
            "refund_id": self.refund_id.id if self.refund_id else False,
            "is_refund": self.is_refund,
            "return_lines": self.return_lines.read(
                [
                    "id",
                    "product_id",
                    "quantity",
                ]
            ),
            "tasting_id": self.tasting_id.id if self.tasting_id else False,
            "is_tasting": self.is_tasting,
            "tasting_lines": self.tasting_lines.read(
                [
                    "id",
                    "product_id",
                    "quantity",
                ]
            ),
        }

    def action_update_status(self, status):
        self.ensure_one()

        if status not in ["pending", "visited", "skipped"]:
            raise exceptions.UserError("Estado inválido.")

        self.status = status
        return True

    def action_remove_product_line(self, line_id):
        self.ensure_one()
        line = self.env["route.sale.product.line"].browse(line_id)
        if line.sale_address_id.id == self.id:
            line.unlink()
        return True

    def action_remove_product_line_refund(self, line_id):
        self.ensure_one()
        line = self.env["route.sale.return.line"].browse(line_id)
        if line.sale_address_id.id == self.id:
            line.unlink()
        return True

    def action_remove_product_line_tasting(self, line_id):
        self.ensure_one()
        line = self.env["route.sale.tasting.line"].browse(line_id)
        if line.sale_address_id.id == self.id:
            line.unlink()
        return True

    def get_available_products(self):
        self.ensure_one()
        all_products = self.route_id.product
        used_ids = self.product_lines.mapped("product_id").ids
        return [
            {"id": p.id, "product_id": [p.id, p.name]}
            for p in all_products
            if p.id not in used_ids
        ]

    def get_available_products_refund(self):
        self.ensure_one()
        all_products = self.route_id.product
        used_ids = self.return_lines.mapped("product_id").ids
        return [
            {"id": p.id, "product_id": [p.id, p.name]}
            for p in all_products
            if p.id not in used_ids
        ]

    def get_available_products_tasting(self):
        self.ensure_one()
        all_products = self.route_id.product
        used_ids = self.tasting_lines.mapped("product_id").ids
        return [
            {"id": p.id, "product_id": [p.id, p.name]}
            for p in all_products
            if p.id not in used_ids
        ]

    def action_add_product_line(self, productId):
        self.ensure_one()
        product = self.env["product.product"].browse(productId)
        line = self.env["route.sale.product.line"].create(
            {
                "sale_address_id": self.id,
                "product_id": product.id,
                "quantity": 0,
            }
        )
        # Retornar igual que action_load_route_products
        return {
            "id": line.id,
            "product_id": [product.id, product.display_name],
            "quantity": line.quantity,
        }

    def action_add_product_line_refund(self, productId):
        self.ensure_one()
        product = self.env["product.product"].browse(productId)
        line = self.env["route.sale.return.line"].create(
            {
                "sale_address_id": self.id,
                "product_id": product.id,
                "quantity": 0,
            }
        )
        # Retornar igual que action_load_route_products
        return {
            "id": line.id,
            "product_id": [product.id, product.display_name],
            "quantity": line.quantity,
        }

    def action_add_product_line_tasting(self, productId):
        self.ensure_one()
        product = self.env["product.product"].browse(productId)
        line = self.env["route.sale.tasting.line"].create(
            {
                "sale_address_id": self.id,
                "product_id": product.id,
                "quantity": 0,
            }
        )
        # Retornar igual que action_load_route_products
        return {
            "id": line.id,
            "product_id": [product.id, product.display_name],
            "quantity": line.quantity,
        }

    def handle_button_sale_terminal(self):
        self.ensure_one()

        order = self.env["sale.order"].create(
            {
                "partner_id": self.contact.id,
                "origin": "Ruta: %s" % (self.route_id.name or ""),
                "warehouse_id": self.route_id.warehouse_id.id,
                "user_id": self.env.user.id,
                "preferred_payment_method_line_id": self.contact.property_inbound_payment_method_line_id.id
                or False,
            }
        )

        for line in self.product_lines:
            if line.quantity > 0:
                self.env["sale.order.line"].create(
                    {
                        "order_id": order.id,
                        "product_id": line.product_id.id,
                        "product_uom_qty": line.quantity,
                        "price_unit": line.product_id.lst_price,
                        "name": line.product_id.name,
                    }
                )

        self.write(
            {
                "sale_order_id": order,
                "status": "visited",
                "delivery_time": fields.Datetime.now(),
            }
        )
        self.generate_ticket()

        return {
            "sale_order_id": order.id,
        }

    def get_geolocation(self):
        self.ensure_one()
        lat = self.contact.partner_latitude or 0
        lng = self.contact.partner_longitude or 0
        return {
            "latitude": lat,
            "longitude": lng,
        }
