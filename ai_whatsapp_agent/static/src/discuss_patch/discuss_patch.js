/** @odoo-module **/

/**
 * Patch del componente ChannelHeader de Discuss para mostrar el panel
 * del agente IA en canales de tipo WhatsApp.
 *
 * El módulo intenta parchear @mail/discuss/core/web/channel_header.
 * Si la ruta cambia en futuras versiones de Odoo, el backend sigue
 * funcionando sin problemas; sólo el panel visual no se muestra.
 */

import { patch } from "@web/core/utils/patch";
import { AIAgentPanel } from "../components/ai_agent_panel/ai_agent_panel";

let ChannelHeader;

// Importación dinámica defensiva: si la ruta no existe el módulo no falla
try {
    // Odoo 17/18/19 - ruta principal
    ({ ChannelHeader } = await odoo.loader.modules.get("@mail/discuss/core/web/channel_header") || {});
} catch (_) {
    // Silenciar error; el componente no estará disponible en esta versión
}

// Intentar ruta alternativa si la primera falló
if (!ChannelHeader) {
    try {
        ({ ChannelHeader } = await odoo.loader.modules.get("@discuss/core/web/channel_header") || {});
    } catch (_) {}
}

if (ChannelHeader) {
    /**
     * Añade el componente AIAgentPanel al conjunto de componentes
     * del ChannelHeader para que pueda usarse en su template.
     */
    patch(ChannelHeader, {
        components: {
            ...ChannelHeader.components,
            AIAgentPanel,
        },
    });

    /**
     * Extiende el prototipo para añadir la propiedad computada
     * que determina si el canal es de tipo WhatsApp.
     */
    patch(ChannelHeader.prototype, {
        get isWhatsAppChannel() {
            // El thread/channel puede estar en props.thread o props.channel según la versión
            const thread = this.props.thread || this.props.channel;
            return thread && (thread.type === "whatsapp" || thread.channel_type === "whatsapp");
        },

        get whatsAppChannelId() {
            const thread = this.props.thread || this.props.channel;
            return thread ? (thread.id || thread.localId) : null;
        },
    });
}
