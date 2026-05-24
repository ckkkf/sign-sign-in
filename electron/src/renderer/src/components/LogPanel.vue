<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Space from "@kousum/semi-ui-vue/dist/space";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import { IconCopy, IconDeleteStroked, IconTerminal } from "@kousum/semi-icons-vue";
import type { LogEntry } from "@shared/types";
import { renderIcon } from "../utils/icons";

defineProps<{
  logs: LogEntry[];
  packetLogs: LogEntry[];
}>();

const emit = defineEmits<{
  (event: "copyLogs"): void;
  (event: "clearLogs"): void;
  (event: "copyPacketSnapshot"): void;
  (event: "clearPacketSnapshot"): void;
}>();
</script>

<template>
  <aside class="log-panel">
    <section class="terminal terminal-main">
      <header class="terminal-head">
        <Space>
          <IconTerminal />
          <span>&gt;_ SYSTEM LOG</span>
        </Space>
        <Space class="terminal-actions">
          <Button size="small" theme="light" :icon="renderIcon(IconCopy)" @click="emit('copyLogs')">复制</Button>
          <Button size="small" theme="light" :icon="renderIcon(IconDeleteStroked)" @click="emit('clearLogs')">清空</Button>
        </Space>
      </header>
      <div class="log-list terminal-body">
        <div v-for="entry in logs" :key="`${entry.time}-${entry.message}`" :class="['log-line', entry.level]">
          <span>{{ entry.time }}</span>
          <strong>{{ entry.level }}</strong>
          <p>{{ entry.message }}</p>
        </div>
        <TypographyText v-if="!logs.length" type="tertiary">暂无日志</TypographyText>
      </div>
    </section>

    <section class="terminal packet-terminal">
      <header class="terminal-head packet-head">
        <Space>
          <IconTerminal />
          <span>&gt;_ PACKET SNAPSHOT</span>
        </Space>
        <Space class="terminal-actions">
          <Button size="small" theme="light" :icon="renderIcon(IconCopy)" @click="emit('copyPacketSnapshot')">复制</Button>
          <Button size="small" theme="light" :icon="renderIcon(IconDeleteStroked)" @click="emit('clearPacketSnapshot')">清空</Button>
        </Space>
      </header>
      <div class="log-list terminal-body">
        <div v-for="entry in packetLogs" :key="`${entry.time}-${entry.message}`" :class="['log-line', entry.level]">
          <span>{{ entry.time }}</span>
          <strong>{{ entry.level }}</strong>
          <p>{{ entry.message }}</p>
        </div>
        <TypographyText v-if="!packetLogs.length" type="tertiary">暂无抓包日志</TypographyText>
      </div>
    </section>
  </aside>
</template>
