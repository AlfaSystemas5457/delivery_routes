from odoo import fields, models, api
from odoo.exceptions import UserError
import base64


class StockPicking(models.Model):
    _inherit = "stock.picking"

    customer_signature = fields.Binary("Firma del cliente", attachment=True)
    signature_date = fields.Datetime("Fecha de firma del cliente")

    def button_validate(self):
        for picking in self:
            if picking.picking_type_code != "outgoing":
                return super(StockPicking, self).button_validate()

            if not picking.customer_signature:
                raise UserError(
                    "Debe obtener la firma del cliente antes de validar la entrega."
                )

            picking.signature_date = fields.Datetime.now()
            return super(StockPicking, self).button_validate()

    def do_print_ticket(self):
        picking_operations_report_ticket = self.env.ref(
            "delivery_routes.action_report_route_sale_delivery_ticket",
            raise_if_not_found=False,
        )
        if not picking_operations_report_ticket:
            raise UserError("No se pudo generar el ticket de entrega.")

        return picking_operations_report_ticket.report_action(self)

    def get_delivery_ticket_pdf(self):
        self.ensure_one()

        report_ref = "delivery_routes.action_report_route_sale_delivery_ticket"
        report = self.env.ref(report_ref, raise_if_not_found=False)

        if not report:
            raise UserError(
                "No se pudo generar el ticket de entrega porque no se encontró el reporte."
            )

        try:
            pdf_content, _ = self.env["ir.actions.report"]._render_qweb_pdf(
                report.report_name, [self.id]
            )
        except Exception as e:
            raise UserError("Error al generar el ticket de entrega: %s" % e)

        ticket_b64 = base64.b64encode(pdf_content).decode("utf-8")

        return {
            "ticket_pdf": ticket_b64,
            "filename": f"delivery_ticket_{self.id}.pdf",
        }
