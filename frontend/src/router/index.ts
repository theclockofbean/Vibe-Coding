import { createRouter, createWebHistory } from "vue-router";

import DebugChat from "@/views/DebugChat/DebugChat.vue";
import EvaluationDashboard from "@/views/EvaluationDashboard/EvaluationDashboard.vue";
import HandoffQueue from "@/views/HandoffQueue/HandoffQueue.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "debug-chat", component: DebugChat },
    { path: "/evaluation", name: "evaluation", component: EvaluationDashboard },
    { path: "/handoff", name: "handoff", component: HandoffQueue },
  ],
});

export default router;
