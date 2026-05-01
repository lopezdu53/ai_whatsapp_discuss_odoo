from odoo import api, fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    is_ai_generated = fields.Boolean(
        string='Generado por IA',
        default=False,
        index=True,
        help='Indica que este mensaje fue generado automáticamente por el agente IA',
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Marcar automáticamente los mensajes generados por el contexto IA
        ai_ctx = self.env.context.get('ai_generated_message', False)
        if ai_ctx:
            for vals in vals_list:
                vals.setdefault('is_ai_generated', True)
        return super().create(vals_list)
