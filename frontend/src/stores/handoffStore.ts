import { reactive } from "vue";

import type { AgentQueryResponse } from "@/types/agent";
import type { HandoffStatus, HandoffTicket } from "@/types/handoff";
import { shortId } from "@/utils/format";

const storageKey = "ai-kb-demo-handoff-tickets";

type HandoffState = {
  items: HandoffTicket[];
};

const state = reactive<HandoffState>({
  items: loadTickets(),
});

export function useHandoffStore() {
  function addFromAgentResponse(
    userMessage: string,
    response: AgentQueryResponse,
  ): HandoffTicket | null {
    const required =
      response.handoff_required ||
      response.needs_handoff ||
      response.answer_handoff_required ||
      response.answer_strategy_mode === "handoff_required";

    if (!required) {
      return null;
    }

    const ticket: HandoffTicket = {
      id: String(response.handoff_ticket_no || response.handoff_ticket_id || shortId("ticket")),
      created_at: new Date().toISOString(),
      user_message: userMessage,
      final_response: response.final_response,
      module: response.selected_module || response.answer_primary_module,
      reason: response.answer_strategy_mode || "handoff_required",
      risk_flags: response.risk_flags ?? [],
      status: "open",
    };

    state.items.unshift(ticket);
    persist();
    return ticket;
  }

  function updateStatus(id: string, status: HandoffStatus): void {
    const item = state.items.find((ticket) => ticket.id === id);
    if (!item) {
      return;
    }

    item.status = status;
    persist();
  }

  return {
    items: state.items,
    addFromAgentResponse,
    updateStatus,
  };
}

function loadTickets(): HandoffTicket[] {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(): void {
  localStorage.setItem(storageKey, JSON.stringify(state.items));
}
