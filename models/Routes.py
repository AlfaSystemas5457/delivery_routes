from odoo import models, fields, api, exceptions
from datetime import datetime, date
import base64
import pytz


class Route(models.Model):
    _name = "route.route"
    _description = "Ruta de venta de los repartidores"
    _inherit = ["mail.thread"]

    user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    name = fields.Char(
        string="Nombre de la Ruta", required=True, default="Borrador", tracking=True
    )
    salesperson_ids = fields.Many2many(
        "res.users", string="Repartidores", tracking=True
    )
    product = fields.Many2many("product.product", string="Productos", tracking=True)
    description = fields.Text(string="Descripción", tracking=True)
    address = fields.Char(string="Primera Dirección", tracking=True)
    route_address_ids = fields.One2many(
        "route.sale.address", "route_id", string="Direcciones", tracking=True
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse", string="Almacenes", ondelete="cascade", tracking=True
    )
    state = fields.Selection(
        [
            ("start", "Sin empezar"),
            ("process", "En proceso"),
            ("end", "Finalizado"),
        ],
        string="Estado",
        default="start",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "route.route.sequence"
                )
        return super().create(vals_list)

    @api.constrains("warehouse_id")
    def _check_single_warehouse(self):
        for record in self:
            if not record.warehouse_id:
                raise exceptions.ValidationError("Solo puedes seleccionar un almacén.")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        DAYS = {
            0: "monday",
            1: "tuesday",
            2: "wednesday",
            3: "thursday",
            4: "friday",
            5: "saturday",
            6: "sunday",
        }

        user_tz = self.env.user.tz or "UTC"
        local_tz = pytz.timezone(user_tz)

        today = DAYS[datetime.now(local_tz).weekday()]

        address = self.env["route.address"].search(
            [("dates", "=", today), ("salesperson_ids.id", "=", self.env.user.id)],
            order="create_date desc",
            limit=1,
        )

        if not address.id:
            raise exceptions.UserError("No se encontraron rutas para hoy.")

        res.update(
            {
                "description": address.description,
                "salesperson_ids": [(6, 0, address.salesperson_ids.ids)],
                "product": [(6, 0, address.product.ids)],
                "warehouse_id": address.warehouse_id.id,
            }
        )

        sale_addresses = []
        for partner in address.route_address_ids:
            sale_addresses.append(
                (
                    0,
                    0,
                    {
                        "contact": partner.id,
                        "address": self.env[
                            "route.sale.address"
                        ]._compute_address_from_contact(partner),
                        "status": "pending",
                    },
                )
            )
        res["route_address_ids"] = sale_addresses

        return res

    def action_process(self):
        for rec in self:
            rec.state = "process"

    def action_end(self):
        for rec in self:
            rec.state = "end"

    def action_start(self):
        for rec in self:
            rec.state = "start"


class RouteSaleAddress(models.Model):
    _name = "route.sale.address"
    _description = "Dirección en Venta"

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
            ("visited", "Visitado con pedido"),
            ("skipped", "Visitado sin pedido"),
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
    ticket_pdf = fields.Binary(string="Ticket PDF", readonly=True)
    current_step = fields.Integer(default=0)

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

    # def action_load_route_products(self):
    #     for record in self:
    #         if record.route_id and not record.product_lines:
    #             product_lines = []
    #             for product in record.route_id.product:
    #                 product_lines.append(
    #                     (0, 0, {"product_id": product.id, "quantity": 0.0})
    #                 )
    #             record.product_lines = product_lines

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

        self.ticket_pdf = base64.b64encode(pdf_content)

    def handle_button_sale(self):
        self.ensure_one()
        self.generate_ticket()

        for record in self:
            order = self.env["sale.order"].create(
                {
                    "partner_id": record.contact.id,
                    "origin": "Ruta: %s" % (record.route_id.name or ""),
                    "warehouse_id": record.route_id.warehouse_id.id,
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

            record.sale_order_id = order
            record.status = "visited"
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

    def get_available_products(self):
        self.ensure_one()
        all_products = self.route_id.product
        used_ids = self.product_lines.mapped("product_id").ids
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

    def handle_button_sale_terminal(self):
        self.ensure_one()
        self.generate_ticket()

        order = self.env["sale.order"].create(
            {
                "partner_id": self.contact.id,
                "origin": "Ruta: %s" % (self.route_id.name or ""),
                "warehouse_id": self.route_id.warehouse_id.id,
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

        self.sale_order_id = order
        self.status = "visited"

        return {
            "sale_order_id": order.id,
        }


class RouteSaleProductLine(models.Model):
    _name = "route.sale.product.line"
    _description = "Línea de productos vendidos en dirección"

    sale_address_id = fields.Many2one(
        "route.sale.address", string="Dirección de Venta", ondelete="cascade"
    )
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    quantity = fields.Float(string="Cantidad", default=1.0)


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
    dates = fields.Selection(
        [
            ("monday", "Lunes"),
            ("tuesday", "Martes"),
            ("wednesday", "Miércoles"),
            ("thursday", "Jueves"),
            ("friday", "Viernes"),
            ("saturday", "Sábado"),
            ("sunday", "Domingo"),
        ],
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
