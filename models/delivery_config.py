from odoo import models, fields


class DeliveryConfig(models.Model):
    _name = "delivery.config"
    _description = "Configuración de Terminal de Ruta"

    name = fields.Char(string="Nombre del Terminal", required=True)
    driver_id = fields.Many2one("res.users", string="Repartidor Asignado")
    # warehouse_id = fields.Many2one("stock.warehouse", string="Almacén de Origen")
    # Agrega campos como 'permitir_devoluciones', 'metodo_pago_id', etc.
    # allow_returns = fields.Boolean(string="Permitir Devoluciones", default=False)
    # payment_method_id = fields.Many2one(
    #     "account.payment.method", string="Método de Pago"
    # )
    # active = fields.Boolean(string="Activo", default=True)
    # sequence = fields.Integer(string="Secuencia", default=10)
    # route_ids = fields.One2many("delivery.route", "config_id", string="Rutas Asociadas")
    # partner_ids = fields.Many2many("res.partner", string="Clientes Asociados")
