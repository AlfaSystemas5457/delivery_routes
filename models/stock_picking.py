from odoo import fields, models, api
from odoo.exceptions import UserError


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
