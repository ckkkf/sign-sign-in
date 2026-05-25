<script setup lang="ts">
import Nav from "@kousum/semi-ui-vue/dist/navigation";
import Button from "@kousum/semi-ui-vue/dist/button";
import { IconHome, IconList, IconSetting, IconUser } from "@kousum/semi-icons-vue";
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

const selectedKeys = computed(() => [props.page]);

function handleSelect(data: any) {
  emit("changePage", data.selectedKeys[0] as PageKey);
}
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
      <Nav
        mode="vertical"
        :selected-keys="selectedKeys"
        :is-collapsed="true"
        @select="handleSelect"
      >
        <Nav.Item
          item-key="dashboard"
          :icon="renderIcon(IconHome, 'default')"
          text="首页"
        />
        <Nav.Item
          item-key="jielong"
          :icon="renderIcon(IconList, 'default')"
          text="接龙"
        />
        <Nav.Item
          item-key="config"
          :icon="renderIcon(IconSetting, 'default')"
          text="配置"
        />
      </Nav>
    </div>
    <div class="rail-spacer" />
  </aside>
</template>
