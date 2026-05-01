from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ai_whatsapp_provider = fields.Selection(
        selection=[
            ('openai', 'OpenAI (GPT-4o, GPT-4, etc.)'),
            ('anthropic', 'Anthropic (Claude)'),
        ],
        string='Proveedor de IA',
        default='openai',
        config_parameter='ai_whatsapp_agent.provider',
    )
    ai_whatsapp_api_key = fields.Char(
        string='API Key',
        config_parameter='ai_whatsapp_agent.api_key',
        help='Clave de API del proveedor seleccionado (OpenAI o Anthropic)',
    )
    ai_whatsapp_model = fields.Char(
        string='Modelo de IA',
        config_parameter='ai_whatsapp_agent.model',
        help='Nombre del modelo: gpt-4o, gpt-4-turbo, claude-sonnet-4-6, etc.',
        placeholder='gpt-4o',
    )
    ai_whatsapp_max_tokens = fields.Integer(
        string='Tokens máximos por respuesta',
        default=500,
        config_parameter='ai_whatsapp_agent.max_tokens',
    )
    ai_whatsapp_temperature = fields.Float(
        string='Temperatura (creatividad)',
        default=0.7,
        config_parameter='ai_whatsapp_agent.temperature',
        help='0.0 = respuestas deterministas, 1.0 = máxima creatividad',
    )
    ai_whatsapp_default_system_prompt = fields.Text(
        string='Prompt del sistema (global)',
        config_parameter='ai_whatsapp_agent.default_system_prompt',
        help='Instrucciones base para la IA en todos los canales WhatsApp. '
             'Cada canal puede sobrescribir esto con su propio prompt.',
    )
    ai_whatsapp_default_timeout = fields.Integer(
        string='Tiempo de inactividad humana (minutos)',
        default=30,
        config_parameter='ai_whatsapp_agent.default_timeout',
        help='Minutos sin respuesta del agente humano para reactivar la IA automáticamente. '
             'Cada canal puede tener su propio valor. 0 = no reactivar automáticamente.',
    )
