from odoo import models, fields, api, exceptions
from datetime import datetime
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
    route_id = fields.Many2one(
        "route.address",
        string="Ruta",
        tracking=True,
    )
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
    amount_total = fields.Float(
        string="Total de la Ruta", compute="_compute_amount_total", store=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    cash_out_report = fields.Binary(string="Reporte de corte", readonly=True)

    @api.depends("route_address_ids.sale_order_id.amount_total")
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(
                [
                    address.sale_order_id.amount_total if address.sale_order_id else 0.0
                    for address in record.route_address_ids
                ]
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

    def _get_route_address_lines_from_route(self, route):
        lines = []
        if not route:
            return lines

        for partner in route.route_address_ids:
            lines.append(
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
        return lines

    def action_reload_route_address_ids(self):
        for rec in self:
            if rec.state != "start":
                raise exceptions.UserError("No se puede modificar en este estado.")

            if not rec.route_id:
                raise exceptions.UserError("No hay ruta seleccionada para recargar.")

            new_lines = rec._get_route_address_lines_from_route(rec.route_id)

            if not new_lines:
                raise exceptions.UserError("La ruta no tiene direcciones para cargar.")

            rec.write({"route_address_ids": [(5, 0, 0)] + new_lines})
        return True

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
            [("dates.code", "=", today), ("salesperson_ids.id", "=", self.env.user.id)],
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
                "route_id": address.id,
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
            if rec.state != "end":
                rec.regenerate_cash_out_report()
                rec.state = "end"
            rec.state = "end"

    def action_start(self):
        for rec in self:
            rec.state = "start"

    def print_cash_out_report(self):
        self.ensure_one()
        if not self.cash_out_report:
            self.regenerate_cash_out_report()

        nombre_archivo = f"Corte_{self.name}.pdf"

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content?model={self._name}&id={self.id}&field=cash_out_report&filename={nombre_archivo}&download=true",
            "target": "self",
        }

    def get_cash_out_report(self):
        self.ensure_one()
        self.regenerate_cash_out_report()

        return {
            "ticket_pdf": self.cash_out_report,
            "filename": f"Corte_{self.name}.pdf",
        }

    def regenerate_cash_out_report(self):
        self.ensure_one()
        pdf_base64 = self.generate_cash_out_report()

        pdf_bytes = base64.b64decode(pdf_base64)

        old = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("name", "=", f"Corte_{self.name}.pdf"),
            ]
        )
        old.unlink()

        attachment = self.env["ir.attachment"].create(
            {
                "name": f"Corte_{self.name}.pdf",
                "type": "binary",
                "datas": base64.b64encode(pdf_bytes),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/pdf",
            }
        )

        self.message_post(
            body="Reporte de corte generado", attachment_ids=[attachment.id]
        )

        self.cash_out_report = pdf_base64

    def generate_cash_out_report(self):
        report_name = "delivery_routes.action_report_route_cash_out"
        report_obj = self.env.ref(report_name)

        pdf_content, content_type = self.env["ir.actions.report"]._render_qweb_pdf(
            report_obj.report_name, [self.id]
        )

        return base64.b64encode(pdf_content).decode("utf-8")
