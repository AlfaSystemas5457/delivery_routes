from odoo import models, fields, api


class ResDays(models.Model):
    _name = "res.days"
    _description = "Día de la semana"

    name = fields.Char(string="Día", compute="_compute_name")
    code = fields.Selection(
        [
            ("monday", "Lunes"),
            ("tuesday", "Martes"),
            ("wednesday", "Miércoles"),
            ("thursday", "Jueves"),
            ("friday", "Viernes"),
            ("saturday", "Sábado"),
            ("sunday", "Domingo"),
        ],
        string="Código",
        required=True,
    )

    @api.depends("code")
    def _compute_name(self):
        for record in self:
            record.name = dict(self._fields["code"].selection).get(record.code)
