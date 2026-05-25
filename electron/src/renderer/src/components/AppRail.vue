<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import { IconHome, IconHomeStroked, IconList, IconOrderedListStroked, IconSetting, IconSettingStroked, IconUser } from "@kousum/semi-icons-vue";
import { computed } from "vue";
import type { AuthUser } from "@shared/types";
import type { PageKey } from "../types/app";
import { renderIcon } from "../utils/icons";
import defaultAvatar from "../assets/default-avatar.png";

const props = defineProps<{
  page: PageKey;
  user?: AuthUser;
  offline: boolean;
}>();

const emit = defineEmits<{
  (event: "changePage", page: PageKey): void;
  (event: "openLogin"): void;
  (event: "logout"): void;
}>();

const displayName = computed(() => {
  if (props.offline) return "离线";
  return props.user?.nickName || props.user?.xybUserName || props.user?.username || "SIGN";
});

const accountName = computed(() => props.user?.username || props.user?.xybUserName || "");
const avatarSrc = computed(() => props.user?.avatar || (props.user ? defaultAvatar : ""));
</script>

<template>
  <aside class="nav">
    <div class="rail-profile" role="button" tabindex="0" @click="emit('openLogin')" @keydown.enter="emit('openLogin')">
      <div class="rail-brand">
        <img v-if="avatarSrc" :src="avatarSrc" :alt="displayName" />
        <IconUser v-else size="default" />
      </div>
      <div class="profile-popover">
        <strong>{{ displayName }}</strong>
        <span v-if="accountName">{{ accountName }}</span>
        <span>{{ offline ? "离线模式" : user ? "已登录" : "未登录" }}</span>
        <button v-if="user" type="button" @click.stop="emit('logout')">退出登录</button>
        <button v-else type="button" @click.stop="emit('openLogin')">登录账号</button>
      </div>
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
      <div :class="['rail-item', { 'is-active': page === 'jielong' }]" data-label="接龙">
        <Button
          class-name="rail-nav-button"
          theme="borderless"
          type="tertiary"
          :icon="renderIcon(page === 'jielong' ? IconList : IconOrderedListStroked, 'default')"
          @click="emit('changePage', 'jielong')"
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
