<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import { IconHome, IconHomeStroked, IconSetting, IconSettingStroked, IconUser } from "@kousum/semi-icons-vue";
import { computed } from "vue";
import type { AuthUser } from "@shared/types";
import type { PageKey } from "../types/app";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  page: PageKey;
  user?: AuthUser;
  offline: boolean;
}>();

const emit = defineEmits<{
  (event: "changePage", page: PageKey): void;
  (event: "openLogin"): void;
}>();

const displayName = computed(() => {
  if (props.offline) return "离线";
  return props.user?.nickName || props.user?.xybUserName || props.user?.username || "SIGN";
});
</script>

<template>
  <aside class="nav">
    <div class="rail-profile" role="button" tabindex="0" @click="emit('openLogin')" @keydown.enter="emit('openLogin')">
      <div class="rail-brand">
        <img v-if="user?.avatar" :src="user.avatar" :alt="displayName" />
        <IconUser v-else size="default" />
      </div>
      <TypographyText class-name="rail-hint">{{ displayName }}</TypographyText>
    </div>

    <div class="rail-nav-shell">
      <div :class="['rail-item', { 'is-active': page === 'dashboard' }]" data-label="首页">
        <Button
          class-name="rail-nav-button"
          theme="borderless"
          type="tertiary"
          :icon="renderIcon(page === 'dashboard' ? IconHome : IconHomeStroked, 'default')"
          @click="emit('changePage', 'dashboard')"
        />
      </div>
      <div :class="['rail-item', { 'is-active': page === 'config' }]" data-label="配置">
        <Button
          class-name="rail-nav-button"
          theme="borderless"
          type="tertiary"
          :icon="renderIcon(page === 'config' ? IconSetting : IconSettingStroked, 'default')"
          @click="emit('changePage', 'config')"
        />
      </div>
    </div>
    <div class="rail-spacer" />
  </aside>
</template>
