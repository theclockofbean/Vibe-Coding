<template>
  <article class="panel rounded-lg p-4">
    <div class="flex items-start justify-between gap-3">
      <div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-sm font-semibold text-slate-950">{{ ticket.id }}</span>
          <IntentBadge :module-name="ticket.module" />
          <span
            class="rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset"
            :class="statusClass"
          >
            {{ ticket.status }}
          </span>
        </div>
        <p class="mt-1 text-xs text-slate-500">
          {{ new Date(ticket.created_at).toLocaleString() }}
        </p>
      </div>
      <select
        :value="ticket.status"
        class="focus-ring rounded-md border border-slate-300 bg-white px-2 py-1 text-sm"
        @change="handleStatusChange"
      >
        <option value="open">open</option>
        <option value="resolved">resolved</option>
        <option value="ignored">ignored</option>
      </select>
    </div>

    <div class="mt-4 grid gap-3 md:grid-cols-2">
      <div>
        <p class="label">user message</p>
        <p class="mt-1 text-sm text-slate-900">{{ ticket.user_message }}</p>
      </div>
      <div>
        <p class="label">reason</p>
        <p class="mt-1 text-sm text-slate-900">{{ ticket.reason || "-" }}</p>
      </div>
    </div>

    <p class="mt-3 line-clamp-3 text-sm leading-6 text-slate-700">
      {{ ticket.final_response }}
    </p>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";

import IntentBadge from "@/components/IntentBadge/IntentBadge.vue";
import type { HandoffStatus, HandoffTicket } from "@/types/handoff";

const props = defineProps<{
  ticket: HandoffTicket;
}>();

const emit = defineEmits<{
  "status-change": [id: string, status: HandoffStatus];
}>();

const statusClass = computed(() => {
  if (props.ticket.status === "resolved") {
    return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  }

  if (props.ticket.status === "ignored") {
    return "bg-slate-100 text-slate-600 ring-slate-200";
  }

  return "bg-red-50 text-red-700 ring-red-200";
});

function handleStatusChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value as HandoffStatus;
  emit("status-change", props.ticket.id, value);
}
</script>
