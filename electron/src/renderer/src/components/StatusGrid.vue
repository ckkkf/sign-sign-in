<script setup lang="ts">
import type { StatusItem } from "../types/app";

defineProps<{
  items: StatusItem[];
}>();
</script>

<template>
  <section class="monitor-box">
    <div v-for="item in items" :key="item.key" :class="['status-cell', `status-${item.tone}`]">
      <span>{{ item.key }}</span>
      <strong>{{ item.value }}</strong>
    </div>
  </section>
</template>
