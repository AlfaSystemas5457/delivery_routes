from odoo import models, fields, api, exceptions
from datetime import datetime


class Route(models.Model):
    _name = 'route.route'
    _description = 'Ruta de venta de los repartidores'

    user_id = fields.Many2one(
        'res.users', string='Responsable', default=lambda self: self.env.user)
    access_scope = fields.Selection([
        ('all', 'Ver todas las rutas'),
        ('assigned', 'Solo ver las asignadas')
    ], string="Alcance de acceso a rutas", related='user_id.access_scope', store=True)
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

    # @api.constrains('product')
    # def _check_single_product(self):
    #     for record in self:
    #         if len(record.product) > 1:
    #             raise exceptions.ValidationError(
    #                 "Solo puedes seleccionar un Producto.")

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

        today = DAYS[datetime.today().weekday()]

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

    def action_start(self):
        for rec in self:
            rec.state = 'process'

    def action_end(self):
        for rec in self:
            rec.state = 'end'


# class RouteRoute(models.Model):
#     _inherit = 'route.route'

#     @api.model
#     def search(self, args, offset=0, limit=None, order=None, count=False):
#         print('\n\nhola!!!!!!!!!!!!\n\n')
#         if self.env.context.get('default_salesperson_ids'):
#             args.append(('salesperson_ids.user_id', '=',
#                         self.env.context['default_salesperson_ids'][0][2][0]))
#         return super(RouteRoute, self).search(args, offset=offset, limit=limit, order=order, count=count)


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

    def _compute_state(self):
        self.state = self.route_id.state

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

    # def handle_button_sale(self):
    #     print(
    #         f'Venta de {[r.display_name for r in self.route_id.product]}!!!!!!!!!!!!!\n')
    def handle_button_sale(self):
        for record in self:
            if not record.contact:
                raise exceptions.UserError("Debes seleccionar un contacto.")

            if not record.route_id.warehouse_id:
                raise exceptions.UserError(
                    "La ruta no tiene asignado un almacén.")

            if not record.product_lines or sum(line.quantity for line in record.product_lines) <= 0:
                raise exceptions.UserError("No se asignaron productos.")

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

    # def action_save_status(self):
    #     for rec in self:
    #         rec.write({'status': rec.status})

    #     return {'type': 'ir.actions.act_window_close'}


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
