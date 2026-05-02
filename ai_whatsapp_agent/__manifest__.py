{
    'name': 'AI WhatsApp Agent',
    'version': '19.0.1.0.0',
    'category': 'Discuss',
    'summary': 'Agente IA para conversaciones WhatsApp con transferencia a agente humano',
    'description': """
        Módulo que añade un agente de IA a las conversaciones de WhatsApp en Odoo Discuss.

        Funcionalidades:
        - El agente IA responde automáticamente a mensajes entrantes de WhatsApp
        - Los agentes humanos pueden pausar la IA para atender la conversación
        - La IA se reactiva automáticamente tras un periodo de inactividad del humano
        - Historial completo de conversación disponible como contexto para la IA
        - Configuración de proveedor IA (OpenAI / Anthropic)
        - Prompt del sistema configurable por canal y globalmente
    """,
    'author': 'Custom',
    'depends': ['mail', 'whatsapp'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/discuss_channel_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
