from odoo import fields, models
from odoo.exceptions import UserError


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
