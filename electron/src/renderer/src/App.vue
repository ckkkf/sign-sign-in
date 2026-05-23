<script setup lang="ts">
import AppRail from "./components/AppRail.vue";
import LogPanel from "./components/LogPanel.vue";
import NoticeBanner from "./components/NoticeBanner.vue";
import { useAppState } from "./composables/useAppState";
import ConfigPage from "./pages/ConfigPage.vue";
import DashboardPage from "./pages/DashboardPage.vue";

const app = useAppState();
</script>

<template>
  <main class="app-shell">
    <section class="layout" :style="{ '--log-panel-width': `${app.logPanelWidth.value}px` }">
      <AppRail
        :page="app.page.value"
        @change-page="(nextPage) => (app.page.value = nextPage)"
        @refresh="app.refreshAll"
      />

      <section class="main-panel">
        <NoticeBanner :boot-error="app.bootError.value" :notice-content="app.noticeContent" />

        <DashboardPage
          v-if="app.page.value === 'dashboard'"
          :action-options="app.actionOptions"
          :capture="app.capture.value"
          :images="app.images.value"
          :is-photo-action="app.isPhotoAction.value"
          :loading="app.loading.value"
          :selected-action="app.selectedAction.value"
          :selected-image="app.selectedImage.value"
          :status="app.status.value"
          :status-items="app.statusItems.value"
          :task="app.task.value"
          @change-page="(nextPage) => (app.page.value = nextPage)"
          @change-selected-action="(value) => (app.selectedAction.value = value)"
          @change-selected-image="(value) => (app.selectedImage.value = value)"
          @copy-q-q-group="app.copyQQGroup"
          @delete-selected-image="app.deleteSelectedImage"
          @import-image="app.importImage"
          @open-cert-manager="app.openCertManager"
          @open-proxy-settings="app.openProxySettings"
          @refresh-all="app.refreshAll"
          @start-capture="app.startCapture"
          @start-task="app.startTask"
          @stop-capture="app.stopCapture"
          @stop-task="app.stopTask"
        />

        <ConfigPage
          v-else
          :draft="app.draft"
          @change-input="app.changeInput"
          @regenerate-user-agent="app.regenerateUserAgent"
          @save-config="app.saveConfig"
        />
      </section>

      <div class="splitter" title="拖动调整日志宽度" @mousedown="app.startResize" />

      <LogPanel
        :logs="app.logs.value"
        :packet-items="app.packetItems.value"
        @copy-logs="app.copyLogs"
        @clear-logs="app.clearLogs"
        @copy-packet-snapshot="app.copyPacketSnapshot"
        @clear-packet-snapshot="app.clearPacketSnapshot"
      />
    </section>
  </main>
</template>
