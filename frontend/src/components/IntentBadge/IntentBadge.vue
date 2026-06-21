<template>
  <span
    class="inline-flex items-center rounded-md px-2 py-1 text-xs font-semibold ring-1 ring-inset"
    :class="moduleClass(moduleName)"
  >
    {{ moduleName || "unknown" }}
  </span>
</template>

<script setup lang="ts">
import { moduleClass } from "@/utils/status";

defineProps<{
  moduleName?: string;
}>();
</script>
