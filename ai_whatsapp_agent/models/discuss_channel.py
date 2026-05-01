import logging
import re
import requests
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    # --- Campos del agente IA ---
    ai_agent_enabled = fields.Boolean(
        string='Agente IA habilitado',
        default=False,
        help='Habilita el agente IA para responder automáticamente mensajes de WhatsApp',
    )
    ai_agent_active = fields.Boolean(
        string='Agente IA activo',
        default=True,
        help='Estado actual del agente IA. False = pausado por agente humano',
    )
    ai_agent_paused_by = fields.Many2one(
        'res.users',
        string='Pausado por',
        readonly=True,
        ondelete='set null',
    )
    ai_agent_paused_at = fields.Datetime(
        string='Fecha de pausa',
        readonly=True,
    )
    last_human_message_at = fields.Datetime(
        string='Último mensaje humano',
        readonly=True,
        help='Timestamp del último mensaje enviado por un agente humano en este canal',
    )
    human_inactivity_timeout = fields.Integer(
        string='Tiempo de inactividad humana (minutos)',
        default=0,
        help='Minutos sin actividad del agente humano para reactivar la IA (0 = usar valor global)',
    )
    ai_system_prompt = fields.Text(
        string='Prompt del sistema (IA)',
        help='Instrucciones personalizadas para la IA en este canal. Deja vacío para usar el prompt global.',
    )
    ai_conversation_summary = fields.Text(
        string='Resumen de conversación',
        readonly=True,
        help='Resumen generado automáticamente del historial de conversación',
    )

    # --- Acciones desde la vista ---

    def action_pause_ai_agent(self):
        for channel in self:
            if not channel.ai_agent_enabled:
                raise UserError(_('El agente IA no está habilitado en este canal.'))
            channel.write({
                'ai_agent_active': False,
                'ai_agent_paused_by': self.env.user.id,
                'ai_agent_paused_at': fields.Datetime.now(),
                'last_human_message_at': fields.Datetime.now(),
            })
            channel.message_post(
                body=_('🤖 Agente IA pausado por <b>%s</b>. Un agente humano atenderá la conversación.') % self.env.user.name,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_resume_ai_agent(self):
        for channel in self:
            if not channel.ai_agent_enabled:
                raise UserError(_('El agente IA no está habilitado en este canal.'))
            channel.write({
                'ai_agent_active': True,
                'ai_agent_paused_by': False,
                'ai_agent_paused_at': False,
                'last_human_message_at': False,
            })
            channel.message_post(
                body=_('🤖 Agente IA reactivado. La IA retomará la conversación.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            # Generar mensaje de bienvenida de retorno si hay historial
            channel._send_ai_resume_greeting()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_enable_ai_agent(self):
        for channel in self:
            channel.write({
                'ai_agent_enabled': True,
                'ai_agent_active': True,
            })
            channel.message_post(
                body=_('🤖 Agente IA habilitado para este canal de WhatsApp.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_disable_ai_agent(self):
        for channel in self:
            channel.write({
                'ai_agent_enabled': False,
                'ai_agent_active': False,
            })
            channel.message_post(
                body=_('🤖 Agente IA deshabilitado para este canal.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # --- Lógica de respuesta automática ---

    def _message_post_after_hook(self, message, msg_values):
        res = super()._message_post_after_hook(message, msg_values)

        # Solo procesar canales WhatsApp con IA habilitada y activa
        if (self.channel_type != 'whatsapp'
                or not self.ai_agent_enabled
                or not self.ai_agent_active
                or message.is_ai_generated):
            return res

        # Ignorar notas internas
        comment_subtype = self.env.ref('mail.mt_comment', raise_if_not_found=False)
        if message.subtype_id != comment_subtype:
            return res

        # Si es mensaje de agente humano interno: actualizar timestamp y NO responder con IA
        if self._is_internal_user_message(message):
            self.write({'last_human_message_at': fields.Datetime.now()})
            return res

        # Mensaje de cliente entrante: generar respuesta IA
        self._generate_ai_response(message)
        return res

    def _is_internal_user_message(self, message):
        """Determina si el autor del mensaje es un usuario interno de Odoo."""
        if not message.author_id:
            return False
        internal_users = message.author_id.user_ids.filtered(
            lambda u: u.has_group('base.group_user') and not u.share
        )
        return bool(internal_users)

    # --- Generación de respuesta IA ---

    def _get_conversation_history(self, limit=30):
        """Construye el historial de conversación para el contexto de la IA."""
        messages = self.env['mail.message'].search([
            ('res_id', '=', self.id),
            ('model', '=', 'discuss.channel'),
            ('message_type', 'in', ['comment', 'email', 'whatsapp_message']),
            ('subtype_id', '=', self.env.ref('mail.mt_comment').id),
        ], limit=limit, order='date asc')

        history = []
        for msg in messages:
            if not msg.body:
                continue
            # Limpiar HTML
            body = re.sub(r'<[^>]+>', ' ', msg.body)
            body = re.sub(r'\s+', ' ', body).strip()
            if not body:
                continue

            if msg.is_ai_generated:
                role = 'assistant'
            elif self._is_internal_user_message(msg):
                # Mensajes de agentes humanos incluidos como "assistant" para dar contexto
                role = 'assistant'
            else:
                role = 'user'

            history.append({'role': role, 'content': body})

        return history

    def _get_effective_system_prompt(self):
        """Devuelve el prompt efectivo: canal > global."""
        if self.ai_system_prompt and self.ai_system_prompt.strip():
            return self.ai_system_prompt.strip()
        config = self.env['ir.config_parameter'].sudo()
        default = config.get_param(
            'ai_whatsapp_agent.default_system_prompt',
            'Eres un asistente de atención al cliente amable y conciso. '
            'Responde siempre en el mismo idioma que el cliente. '
            'Si no puedes resolver algo, ofrece transferir con un agente humano.'
        )
        return default

    def _get_ai_config(self):
        """Lee la configuración del proveedor IA."""
        config = self.env['ir.config_parameter'].sudo()
        return {
            'provider': config.get_param('ai_whatsapp_agent.provider', 'openai'),
            'api_key': config.get_param('ai_whatsapp_agent.api_key', ''),
            'model': config.get_param('ai_whatsapp_agent.model', 'gpt-4o'),
            'max_tokens': int(config.get_param('ai_whatsapp_agent.max_tokens', '500')),
            'temperature': float(config.get_param('ai_whatsapp_agent.temperature', '0.7')),
        }

    def _generate_ai_response(self, trigger_message):
        """Genera y publica la respuesta de la IA."""
        try:
            ai_config = self._get_ai_config()
            if not ai_config['api_key']:
                _logger.warning(
                    'AI WhatsApp Agent [canal %s]: Sin API key configurada. '
                    'Configure una en Ajustes > Agente IA WhatsApp.',
                    self.id
                )
                return

            system_prompt = self._get_effective_system_prompt()
            history = self._get_conversation_history()

            if not history:
                return

            provider = ai_config['provider']
            if provider == 'openai':
                response_text = self._call_openai(ai_config, system_prompt, history)
            elif provider == 'anthropic':
                response_text = self._call_anthropic(ai_config, system_prompt, history)
            else:
                _logger.error('AI WhatsApp Agent: proveedor desconocido "%s"', provider)
                return

            if response_text:
                self._post_ai_message(response_text)

        except requests.exceptions.Timeout:
            _logger.error('AI WhatsApp Agent [canal %s]: Timeout al llamar a la API de IA', self.id)
        except requests.exceptions.HTTPError as exc:
            _logger.error(
                'AI WhatsApp Agent [canal %s]: Error HTTP %s - %s',
                self.id, exc.response.status_code, exc.response.text[:500]
            )
        except Exception:
            _logger.exception('AI WhatsApp Agent [canal %s]: Error inesperado generando respuesta', self.id)

    def _call_openai(self, ai_config, system_prompt, history):
        """Llama a la API de OpenAI."""
        headers = {
            'Authorization': f'Bearer {ai_config["api_key"]}',
            'Content-Type': 'application/json',
        }
        messages = [{'role': 'system', 'content': system_prompt}] + history

        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json={
                'model': ai_config['model'] or 'gpt-4o',
                'messages': messages,
                'max_tokens': ai_config['max_tokens'],
                'temperature': ai_config['temperature'],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content'].strip()

    def _call_anthropic(self, ai_config, system_prompt, history):
        """Llama a la API de Anthropic."""
        headers = {
            'x-api-key': ai_config['api_key'],
            'anthropic-version': '2023-06-01',
            'Content-Type': 'application/json',
        }
        # Anthropic requiere que el primer mensaje sea 'user'
        clean_history = history[:]
        if clean_history and clean_history[0]['role'] == 'assistant':
            clean_history = clean_history[1:]

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json={
                'model': ai_config['model'] or 'claude-sonnet-4-6',
                'system': system_prompt,
                'messages': clean_history,
                'max_tokens': ai_config['max_tokens'],
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data['content'][0]['text'].strip()

    def _post_ai_message(self, text):
        """Publica el mensaje de la IA en el canal con la marca is_ai_generated."""
        self.with_context(
            mail_create_nosubscribe=True,
            ai_generated_message=True,
        ).message_post(
            body=text,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            author_id=self.env.ref('base.partner_root').id,
        )

    def _send_ai_resume_greeting(self):
        """Cuando la IA se reactiva, genera un saludo de retorno si hay historial."""
        try:
            ai_config = self._get_ai_config()
            if not ai_config['api_key']:
                return

            history = self._get_conversation_history(limit=10)
            if not history:
                return

            system_prompt = self._get_effective_system_prompt()
            resume_instruction = (
                system_prompt + '\n\n'
                'IMPORTANTE: Acabo de retomar la conversación después de que un agente humano '
                'la atendió por un momento. Saluda brevemente al cliente y ofrece continuar ayudándole, '
                'haciendo referencia al contexto de la conversación si es relevante.'
            )

            provider = ai_config['provider']
            if provider == 'openai':
                response_text = self._call_openai(ai_config, resume_instruction, history)
            elif provider == 'anthropic':
                response_text = self._call_anthropic(ai_config, resume_instruction, history)
            else:
                return

            if response_text:
                self._post_ai_message(response_text)

        except Exception:
            _logger.exception('AI WhatsApp Agent [canal %s]: Error al generar saludo de retorno', self.id)

    # --- Cron: reactivación por inactividad humana ---

    @api.model
    def _cron_resume_ai_after_inactivity(self):
        """
        Revisa canales con IA pausada por agente humano.
        Si el tiempo de inactividad supera el umbral, reactiva la IA.
        """
        config = self.env['ir.config_parameter'].sudo()
        global_timeout = int(config.get_param('ai_whatsapp_agent.default_timeout', '30'))

        channels = self.search([
            ('channel_type', '=', 'whatsapp'),
            ('ai_agent_enabled', '=', True),
            ('ai_agent_active', '=', False),
            ('last_human_message_at', '!=', False),
        ])

        now = fields.Datetime.now()
        for channel in channels:
            timeout_minutes = channel.human_inactivity_timeout or global_timeout
            if timeout_minutes <= 0:
                continue

            threshold = channel.last_human_message_at + timedelta(minutes=timeout_minutes)
            if now >= threshold:
                _logger.info(
                    'AI WhatsApp Agent: Reactivando IA en canal %s '
                    '(%s minutos de inactividad humana)',
                    channel.id, timeout_minutes
                )
                channel.action_resume_ai_agent()

    # --- Datos para el panel OWL ---

    def _get_ai_agent_info(self):
        """Retorna información del estado del agente IA para el frontend."""
        self.ensure_one()
        return {
            'enabled': self.ai_agent_enabled,
            'active': self.ai_agent_active,
            'paused_by': self.ai_agent_paused_by.name if self.ai_agent_paused_by else False,
            'paused_at': fields.Datetime.to_string(self.ai_agent_paused_at) if self.ai_agent_paused_at else False,
            'timeout': self.human_inactivity_timeout,
        }
