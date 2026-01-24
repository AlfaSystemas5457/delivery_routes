from odoo import fields, models
from odoo.exceptions import UserError
import base64


class AccountMove(models.Model):
    _inherit = "account.move"

    def do_print_ticket(self):
        invoice_report_ticket = self.env.ref(
            "delivery_routes.action_report_route_sale_invoice_ticket",
            raise_if_not_found=False,
        )
        if not invoice_report_ticket:
            raise UserError("No se pudo generar el ticket de factura.")

        return invoice_report_ticket.report_action(self)

    def get_invoice_ticket_pdf(self):
        self.ensure_one()

        invoice_report_xmlid = "delivery_routes.action_report_route_sale_invoice_ticket"
        report = self.env.ref(invoice_report_xmlid, raise_if_not_found=False)

        if not report:
            raise UserError(
                "No se pudo generar el ticket de factura (no se encontró el reporte)."
            )

        try:
            pdf_content, _ = self.env["ir.actions.report"]._render_qweb_pdf(
                report.report_name, [self.id]
            )
        except Exception as e:
            raise UserError(f"Error al generar el ticket de factura: {e}")

        ticket_b64 = base64.b64encode(pdf_content).decode("utf-8")

        return {
            "ticket_pdf": ticket_b64,
            "filename": f"invoice_ticket_{self.id}.pdf",
        }
