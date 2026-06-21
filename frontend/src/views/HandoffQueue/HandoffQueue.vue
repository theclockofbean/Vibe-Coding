<template>
  <div class="space-y-5">
    <section class="grid gap-4 md:grid-cols-3">
      <MetricCard label="open" :value="openCount" />
      <MetricCard label="resolved" :value="resolvedCount" />
      <MetricCard label="ignored" :value="ignoredCount" />
    </section>

    <section class="space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-slate-950">本地 Demo 工单</h2>
          <p class="mt-1 text-sm text-slate-500">
            由对话响应中的 handoff 字段自动生成。
          </p>
        </div>
        <select
          v-model="status"
          class="focus-ring rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">all</option>
          <option value="open">open</option>
          <option value="resolved">resolved</option>
          <option value="ignored">ignored</option>
        </select>
      </div>

      <div v-if="filteredTickets.length" class="space-y-3">
        <HandoffCard
          v-for="ticket in filteredTickets"
          :key="ticket.id"
          :ticket="ticket"
          @status-change="updateStatus"
        />
      </div>
      <div v-else class="panel rounded-lg p-6 text-sm text-slate-500">
        暂无工单。到对话调试页发送价格、质量承诺或售后类问题即可生成。
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import HandoffCard from "@/components/HandoffCard/HandoffCard.vue";
import MetricCard from "@/components/ConfidenceIndicator/MetricCard.vue";
import { useHandoffStore } from "@/stores/handoffStore";
import type { HandoffStatus } from "@/types/handoff";

const store = useHandoffStore();
const status = ref("");

const filteredTickets = computed(() =>
  status.value ? store.items.filter((item) => item.status === status.value) : store.items,
);
const openCount = computed(() => store.items.filter((item) => item.status === "open").length);
const resolvedCount = computed(
  () => store.items.filter((item) => item.status === "resolved").length,
);
const ignoredCount = computed(
  () => store.items.filter((item) => item.status === "ignored").length,
);

function updateStatus(id: string, nextStatus: HandoffStatus): void {
  store.updateStatus(id, nextStatus);
}
</script>
