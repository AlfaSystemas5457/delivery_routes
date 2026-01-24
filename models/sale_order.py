from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_create_invoice_rpc(self):
        wizard = (
            self.env["sale.advance.payment.inv"]
            .with_context(
                active_ids=self.ids,
                active_model="sale.order",
                active_id=self.id,
            )
            .create(
                {
                    "advance_payment_method": "delivered",
                }
            )
        )

        wizard.create_invoices()

        return [
            invoice.id
            for invoice in self.mapped("invoice_ids")
            if invoice.state != "cancel"
        ]

    def get_invoices_rpc(self):
        return [
            invoice.id
            for invoice in self.mapped("invoice_ids")
            if invoice.state != "cancel"
        ]
