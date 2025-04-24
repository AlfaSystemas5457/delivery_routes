from odoo import fields, models


class Contact(models.Model):
    _inherit = 'res.partner'

    salesperson = fields.Many2many('hr.employee', string='Proveedor')
