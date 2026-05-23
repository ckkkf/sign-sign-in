<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import { IconHomeStroked, IconRefresh, IconSetting, IconUser } from "@kousum/semi-icons-vue";
import type { PageKey } from "../types/app";
import { renderIcon } from "../utils/icons";

defineProps<{
  page: PageKey;
}>();

const emit = defineEmits<{
  (event: "changePage", page: PageKey): void;
  (event: "refresh"): void;
}>();
</script>

<template>
  <aside class="nav">
    <div class="rail-brand">
      <IconUser size="default" />
    </div>
    <TypographyText class-name="rail-hint">SIGN</TypographyText>
    <div class="rail-nav-shell">
      <Button
        class-name="rail-nav-button"
        :theme="page === 'dashboard' ? 'solid' : 'light'"
        type="primary"
        :icon="renderIcon(IconHomeStroked)"
        @click="emit('changePage', 'dashboard')"
      />
      <Button
        class-name="rail-nav-button"
        :theme="page === 'config' ? 'solid' : 'light'"
        type="primary"
        :icon="renderIcon(IconSetting)"
        @click="emit('changePage', 'config')"
      />
    </div>
    <div class="rail-spacer" />
    <Button class-name="rail-nav-button" theme="light" type="primary" :icon="renderIcon(IconRefresh)" @click="emit('refresh')" />
  </aside>
</template>
