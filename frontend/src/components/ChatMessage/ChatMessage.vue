<template>
  <article
    class="flex"
    :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[86%] rounded-lg border px-4 py-3 text-sm leading-6"
      :class="
        message.role === 'user'
          ? 'border-sky-200 bg-sky-50 text-sky-950'
          : 'border-slate-200 bg-white text-slate-900'
      "
    >
      <div class="whitespace-pre-wrap break-words">{{ message.content }}</div>
      <div
        v-if="message.response"
        class="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200 pt-2"
      >
        <IntentBadge :module-name="message.response.selected_module" />
        <span
          v-if="message.response.answer_strategy_mode"
          class="inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset"
          :class="strategyClass(message.response.answer_strategy_mode)"
        >
          {{ message.response.answer_strategy_mode }}
        </span>
        <span
          v-if="handoff"
          class="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-semibold text-red-700 ring-1 ring-inset ring-red-200"
        >
          handoff
        </span>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";

import IntentBadge from "@/components/IntentBadge/IntentBadge.vue";
import type { ChatMessage } from "@/types/agent";
import { strategyClass } from "@/utils/status";

const props = defineProps<{
  message: ChatMessage;
}>();

const handoff = computed(() => {
  const response = props.message.response;
  return Boolean(
    response?.handoff_required ||
      response?.needs_handoff ||
      response?.answer_handoff_required,
  );
});
</script>
