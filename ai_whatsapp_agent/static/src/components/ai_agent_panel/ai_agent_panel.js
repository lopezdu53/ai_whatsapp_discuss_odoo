/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime } from "@web/core/l10n/dates";

export class AIAgentPanel extends Component {
    static template = "ai_whatsapp_agent.AIAgentPanel";
    static props = {
        channelId: { type: Number },
        onStatusChange: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            enabled: false,
            active: false,
            paused_by: false,
            paused_at: false,
            timeout: 30,
            loading: false,
            expanded: true,
        });

        onWillStart(async () => {
            await this._loadStatus();
        });
    }

    async _loadStatus() {
        try {
            const result = await this.orm.call(
                "discuss.channel",
                "_get_ai_agent_info",
                [this.props.channelId]
            );
            Object.assign(this.state, result);
        } catch (e) {
            console.error("AI Agent Panel: Error cargando estado", e);
        }
    }

    get statusLabel() {
        if (!this.state.enabled) return _t("Deshabilitado");
        if (this.state.active) return _t("Activo");
        return _t("Pausado");
    }

    get statusClass() {
        if (!this.state.enabled) return "o_ai_status_disabled";
        if (this.state.active) return "o_ai_status_active";
        return "o_ai_status_paused";
    }

    get pausedInfo() {
        if (!this.state.paused_by) return "";
        let info = _t("Pausado por: ") + this.state.paused_by;
        if (this.state.paused_at) {
            info += " · " + this.state.paused_at;
        }
        return info;
    }

    async onClickPause() {
        this.state.loading = true;
        try {
            await this.orm.call(
                "discuss.channel",
                "action_pause_ai_agent",
                [[this.props.channelId]]
            );
            this.notification.add(_t("Agente IA pausado. Un humano puede atender la conversación."), {
                type: "warning",
            });
            await this._loadStatus();
            if (this.props.onStatusChange) {
                this.props.onStatusChange();
            }
        } catch (e) {
            this.notification.add(_t("Error al pausar el agente IA."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onClickResume() {
        this.state.loading = true;
        try {
            await this.orm.call(
                "discuss.channel",
                "action_resume_ai_agent",
                [[this.props.channelId]]
            );
            this.notification.add(_t("Agente IA reactivado. La IA continuará la conversación."), {
                type: "success",
            });
            await this._loadStatus();
            if (this.props.onStatusChange) {
                this.props.onStatusChange();
            }
        } catch (e) {
            this.notification.add(_t("Error al reactivar el agente IA."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onClickEnable() {
        this.state.loading = true;
        try {
            await this.orm.call(
                "discuss.channel",
                "action_enable_ai_agent",
                [[this.props.channelId]]
            );
            this.notification.add(_t("Agente IA habilitado para este canal."), {
                type: "success",
            });
            await this._loadStatus();
        } catch (e) {
            this.notification.add(_t("Error al habilitar el agente IA."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async onClickDisable() {
        this.state.loading = true;
        try {
            await this.orm.call(
                "discuss.channel",
                "action_disable_ai_agent",
                [[this.props.channelId]]
            );
            this.notification.add(_t("Agente IA deshabilitado."), { type: "info" });
            await this._loadStatus();
        } catch (e) {
            this.notification.add(_t("Error al deshabilitar el agente IA."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    toggleExpanded() {
        this.state.expanded = !this.state.expanded;
    }
}
