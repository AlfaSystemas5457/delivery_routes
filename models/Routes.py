from odoo import models, fields, api, exceptions
from datetime import datetime
import base64
import pytz


class Route(models.Model):
    _name = 'route.route'
    _description = 'Ruta de venta de los repartidores'
    _inherit = ['mail.thread']

    user_id = fields.Many2one(
        'res.users', string='Responsable', default=lambda self: self.env.user)
    name = fields.Char(
        string='Nombre de la Ruta',
        required=True,
        default='Borrador')
    salesperson_ids = fields.Many2many('hr.employee', string='Repartidores')
    product = fields.Many2many(
        'product.product', string='Productos')
    description = fields.Text(string='Descripción')
    address = fields.Char(string='Primera Dirección')
    route_address_ids = fields.One2many(
        'route.sale.address',
        'route_id',
        string='Direcciones')
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Almacenes', ondelete='cascade')
    state = fields.Selection([
        ('start', 'Sin empezar'),
        ('process', 'En proceso'),
        ('end', 'Finalizado'),
    ], string='Estado', default='start')

    @api.model
    def create(self, vals):
        if self.env.user.access_scope != 'assigned':
            raise exceptions.AccessError("No tienes permiso para crear rutas.")

        if not vals.get('name'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'route.route.sequence')
        return super().create(vals)

    @api.constrains('warehouse_id')
    def _check_single_warehouse(self):
        for record in self:
            if len(record.warehouse_id) > 1:
                raise exceptions.ValidationError(
                    "Solo puedes seleccionar un almacén.")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        DAYS = {
            0: 'monday',
            1: 'tuesday',
            2: 'wednesday',
            3: 'thursday',
            4: 'friday',
            5: 'saturday',
            6: 'sunday'
        }

        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        today = DAYS[datetime.now(local_tz).weekday()]

        address = self.env['route.address'].search(
            [
                ('dates', '=', today),
                ('salesperson_ids.user_id', '=', self.env.user.id)
            ],
            order="create_date desc",
            limit=1
        )

        if not address.id:
            raise exceptions.UserError('No se encontraron rutas para hoy.')

        res.update({
            'description': address.description,
            'salesperson_ids': [(6, 0, address.salesperson_ids.ids)],
            'product': [(6, 0, address.product.ids)],
            'warehouse_id': address.warehouse_id.id,
        })

        sale_addresses = []
        for partner in address.route_address_ids:
            sale_addresses.append((0, 0, {
                'contact': partner.id,
                'address': self.env['route.sale.address']._compute_address_from_contact(partner),
                'status': 'pending',
            }))
        res['route_address_ids'] = sale_addresses

        return res

    def action_process(self):
        for rec in self:
            rec.state = 'process'

    def action_end(self):
        for rec in self:
            rec.state = 'end'

    def action_start(self):
        for rec in self:
            rec.state = 'start'


class RouteSaleAddress(models.Model):
    _name = 'route.sale.address'
    _description = 'Dirección en Venta'

    address = fields.Char(string='Dirección')
    contact = fields.Many2one(
        'res.partner', string='Contacto', ondelete='cascade')
    route_id = fields.Many2one(
        'route.route', string='Ruta', ondelete='cascade', index=True)
    product_lines = fields.One2many(
        'route.sale.product.line', 'sale_address_id', string='Productos vendidos')
    sale_order_id = fields.Many2one(
        'sale.order', string='Cotización Generada', readonly=True)
    status = fields.Selection([
        ('pending', 'Pendiente'),
        ('visited', 'Visitado con pedido'),
        ('skipped', 'Visitado sin pedido'),
    ], string='Estado', default='pending', required=True)
    state = fields.Selection([
        ('start', 'Sin empezar'),
        ('process', 'En proceso'),
        ('end', 'Finalizado'),
    ], string='Estado', compute="_compute_state")
    ticket_pdf = fields.Binary(string="Ticket PDF", readonly=True)

    def _compute_state(self):
        self.state = self.route_id.state

    def _validations(self):
        if not self.contact:
            raise exceptions.UserError("Debes seleccionar un contacto.")

        if not self.route_id.warehouse_id:
            raise exceptions.UserError(
                "La ruta no tiene asignado un almacén.")

        if not self.product_lines or sum(line.quantity for line in self.product_lines) <= 0:
            raise exceptions.UserError("No se asignaron productos.")

    def action_load_route_products(self):
        for record in self:
            if record.route_id and not record.product_lines:
                product_lines = []
                for product in record.route_id.product:
                    product_lines.append((0, 0, {
                        'product_id': product.id,
                        'quantity': 0.0
                    }))
                record.product_lines = product_lines

    def handle_button_ticket(self):
        self.ensure_one()
        self.generate_ticket()
        return self.env.ref('delivery_routes.action_report_route_sale_address').report_action(self)

    def generate_ticket(self):
        self.ensure_one()

        self._validations()

        report_name = 'delivery_routes.action_report_route_sale_address'
        report_obj = self.env.ref(report_name)

        pdf_content, content_type = self.env['ir.actions.report']._render_qweb_pdf(
            report_obj.report_name, [self.id]
        )

        self.ticket_pdf = base64.b64encode(pdf_content)

    def handle_button_sale(self):
        self.ensure_one()
        self.generate_ticket()

        for record in self:
            order = self.env['sale.order'].create({
                'partner_id': record.contact.id,
                'origin': 'Ruta: %s' % (record.route_id.name or ''),
                'warehouse_id': record.route_id.warehouse_id.id,
            })

            for line in record.product_lines:
                if line.quantity > 0:
                    self.env['sale.order.line'].create({
                        'order_id': order.id,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'price_unit': line.product_id.lst_price,
                        'name': line.product_id.name,
                    })

            record.sale_order_id = order
            record.status = 'visited'
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': order.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def handle_cancel(self):
        return {'type': 'ir.actions.act_window_close'}

    def handle_skipped(self):
        self.status = 'skipped'
        return {'type': 'ir.actions.act_window_close'}

    def _compute_address_from_contact(self, contact):
        return ' '.join(filter(None, [
            contact.street,
            contact.street2,
            contact.city,
            contact.state_id.name,
            contact.zip
        ]))

    @api.onchange('contact')
    def _onchange_contact(self):
        if self.contact:
            self.address = self._compute_address_from_contact(self.contact)

    @api.model
    def create(self, vals):
        if vals.get('contact') and not vals.get('address'):
            contact = self.env['res.partner'].browse(vals['contact'])
            vals['address'] = self._compute_address_from_contact(contact)
        return super().create(vals)

    def write(self, vals):
        if vals.get('contact') and not vals.get('address'):
            contact = self.env['res.partner'].browse(vals['contact'])
            vals['address'] = self._compute_address_from_contact(contact)
        return super().write(vals)


class RouteSaleProductLine(models.Model):
    _name = 'route.sale.product.line'
    _description = 'Línea de productos vendidos en dirección'

    sale_address_id = fields.Many2one(
        'route.sale.address', string='Dirección de Venta', ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', string='Producto', required=True)
    quantity = fields.Float(string='Cantidad', default=1.0)


class Address(models.Model):
    _name = 'route.address'
    _description = 'Dirección de visita'

    name = fields.Char(string='Nombre de la Ruta', required=True)
    description = fields.Text(string='Descripción')
    salesperson_ids = fields.Many2many(
        'hr.employee', string='Repartidores', ondelete='cascade', required=True)
    product = fields.Many2many(
        'product.product', string='Productos', required=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Almacenes', ondelete='cascade', required=True)
    route_address_ids = fields.Many2many(
        'res.partner', ondelete='cascade', string='Direcciones', required=True)
    dates = fields.Selection([
        ('monday', 'Lunes'),
        ('tuesday', 'Martes'),
        ('wednesday', 'Miércoles'),
        ('thursday', 'Jueves'),
        ('friday', 'Viernes'),
        ('saturday', 'Sábado'),
        ('sunday', 'Domingo'),
    ], string='Día', required=True)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        employee = self.env['hr.employee'].search(
            [('user_id', '=', self.env.user.id)], limit=1)

        if employee:
            res['salesperson_ids'] = [(6, 0, [employee.id])]

        return res
