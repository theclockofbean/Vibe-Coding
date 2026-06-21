<template>
  <div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
    <section class="panel flex min-h-[calc(100vh-128px)] flex-col rounded-lg">
      <div class="border-b border-slate-200 p-4">
        <div class="grid gap-3 md:grid-cols-[1fr_160px_160px]">
          <label class="block">
            <span class="label">session</span>
            <input
              v-model="sessionId"
              class="focus-ring mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label class="block">
            <span class="label">channel</span>
            <select
              v-model="channel"
              class="focus-ring mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="local_debug">local_debug</option>
              <option value="wechat">wechat</option>
              <option value="taobao">taobao</option>
              <option value="alibaba">alibaba</option>
            </select>
          </label>
          <label class="block">
            <span class="label">limit</span>
            <input
              v-model.number="limit"
              type="number"
              min="1"
              max="20"
              class="focus-ring mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
      </div>

      <div class="flex-1 space-y-4 overflow-y-auto p-4">
        <ChatMessage v-for="item in messages" :key="item.id" :message="item" />
      </div>

      <div class="border-t border-slate-200 p-4">
        <div class="mb-3 flex flex-wrap gap-2">
          <button
            v-for="question in demoQuestions"
            :key="question"
            class="focus-ring rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
            type="button"
            @click="draft = question"
          >
            {{ question }}
          </button>
        </div>

        <form class="flex gap-3" @submit.prevent="sendMessage">
          <textarea
            v-model="draft"
            class="focus-ring min-h-12 flex-1 resize-none rounded-md border border-slate-300 px-3 py-3 text-sm"
            placeholder="输入测试问题"
            rows="2"
          />
          <button
            class="focus-ring w-24 rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="submit"
            :disabled="loading || !draft.trim()"
          >
            {{ loading ? "发送中" : "发送" }}
          </button>
        </form>
        <p v-if="error" class="mt-2 text-sm text-red-600">{{ error }}</p>
      </div>
    </section>

    <aside class="space-y-4">
      <section class="panel rounded-lg p-4">
        <div class="flex items-center justify-between">
          <h2 class="text-sm font-semibold text-slate-950">结构化调试</h2>
          <span
            v-if="latestResponse"
            class="rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset"
            :class="strategyClass(latestResponse.answer_strategy_mode)"
          >
            {{ latestResponse.answer_strategy_mode || "n/a" }}
          </span>
        </div>

        <dl v-if="latestResponse" class="mt-4 space-y-3">
          <div v-for="item in debugRows" :key="item.label">
            <dt class="label">{{ item.label }}</dt>
            <dd class="mt-1 break-words text-sm font-medium text-slate-900">
              {{ item.value }}
            </dd>
          </div>
        </dl>
        <p v-else class="mt-4 text-sm text-slate-500">等待第一次响应。</p>
      </section>

      <SourceReference :sources="latestResponse?.sources || []" />

      <section class="panel rounded-lg p-4">
        <p class="label">metadata</p>
        <pre
          class="mt-2 max-h-[360px] overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-slate-100"
        >{{ prettyMetadata }}</pre>
      </section>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";

import { queryAgent } from "@/api/agent";
import ChatMessage from "@/components/ChatMessage/ChatMessage.vue";
import SourceReference from "@/components/SourceReference/SourceReference.vue";
import { useHandoffStore } from "@/stores/handoffStore";
import type { AgentQueryResponse, ChatMessage as ChatMessageType } from "@/types/agent";
import { shortId } from "@/utils/format";
import { strategyClass } from "@/utils/status";

const demoQuestions = [
  "SKU001的螺纹规格是多少",
  "你们有没有M14螺纹的球头",
  "夜光系列的球头螺纹规格都一样吗",
  "SKU001几天发货",
  "这个能不能便宜点",
  "这个球头会不会生锈",
];

const draft = ref(demoQuestions[0]);
const loading = ref(false);
const error = ref("");
const channel = ref<"local_debug" | "wechat" | "taobao" | "alibaba">("local_debug");
const sessionId = ref("demo_session_001");
const limit = ref(5);
const messages = ref<ChatMessageType[]>([]);
const latestResponse = ref<AgentQueryResponse | null>(null);
const handoffStore = useHandoffStore();

const debugRows = computed(() => {
  const response = latestResponse.value;
  if (!response) {
    return [];
  }

  return [
    ["selected_module", response.selected_module],
    ["answer_strategy_mode", response.answer_strategy_mode],
    [
      "handoff_required / needs_handoff",
      Boolean(
        response.handoff_required ||
          response.needs_handoff ||
          response.answer_handoff_required,
      ),
    ],
    [
      "answer_safety_blocked / render_safety_blocked",
      Boolean(response.answer_safety_blocked || response.render_safety_blocked),
    ],
    ["render_mode", response.render_mode],
    ["used_llm_output", response.used_llm_output],
    ["retrieved_chunk_count", response.retrieved_chunk_count],
    ["latency_ms", response.latency_ms],
    ["risk_flags", response.risk_flags?.join(", ")],
    ["response_warnings", response.response_warnings?.join(", ")],
  ].map(([label, value]) => ({
    label: String(label),
    value: value === undefined || value === "" ? "-" : String(value),
  }));
});

const prettyMetadata = computed(() => {
  if (!latestResponse.value) {
    return "{}";
  }

  return JSON.stringify(latestResponse.value.metadata || latestResponse.value.raw, null, 2);
});

async function sendMessage(): Promise<void> {
  const message = draft.value.trim();
  if (!message || loading.value) {
    return;
  }

  error.value = "";
  loading.value = true;
  messages.value.push({
    id: shortId("user"),
    role: "user",
    content: message,
    created_at: new Date().toISOString(),
  });

  try {
    const response = await queryAgent({
      message,
      channel: channel.value,
      user_id: "demo_user",
      conversation_id: sessionId.value,
      limit: limit.value,
    });

    latestResponse.value = response;
    if (response.session_id) {
      sessionId.value = response.session_id;
    }

    messages.value.push({
      id: shortId("assistant"),
      role: "assistant",
      content: response.final_response || "后端没有返回 final_response。",
      created_at: new Date().toISOString(),
      response,
    });
    handoffStore.addFromAgentResponse(message, response);
    draft.value = "";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "请求失败";
  } finally {
    loading.value = false;
  }
}
</script>
