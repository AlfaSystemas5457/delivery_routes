from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_scope = fields.Selection([
        ('all', 'Ver todas las rutas'),
        ('assigned', 'Solo ver las asignadas')
    ], string="Alcance de acceso a rutas", default='assigned', required=True, store=True)
