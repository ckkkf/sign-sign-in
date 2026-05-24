<script setup lang="ts">
import AppRail from "./components/AppRail.vue";
import LoginDialog from "./components/LoginDialog.vue";
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
        :user="app.authState.value.user"
        :offline="app.offlineMode.value"
        @change-page="(nextPage) => (app.page.value = nextPage)"
        @open-login="app.openLoginIfLoggedOut"
      />

      <section class="workspace">
        <div class="banner-stack">
          <NoticeBanner :boot-error="app.bootError.value" :notice-content="app.noticeContent" />
        </div>

        <section class="workspace-body">
          <section class="main-panel">
            <button v-if="app.offlineMode.value" class="offline-banner" type="button" @click="app.openLoginIfLoggedOut">离线模式</button>
            <div class="main-content-pad">
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
                @refresh-all="app.manualRefreshAll"
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
            </div>
          </section>

          <div class="splitter" title="拖动调整日志宽度" @mousedown="app.startResize" />

          <LogPanel
            :logs="app.logs.value"
            :packet-logs="app.packetLogs.value"
            @copy-logs="app.copyLogs"
            @clear-logs="app.clearLogs"
            @copy-packet-snapshot="app.copyPacketSnapshot"
            @clear-packet-snapshot="app.clearPacketSnapshot"
          />
        </section>
      </section>

      <LoginDialog
        :visible="app.loginVisible.value"
        :loading="app.loginLoading.value"
        :register-loading="app.registerLoading.value"
        :captcha-loading="app.captchaLoading.value"
        :captcha="app.authCaptcha.value"
        @login="app.login"
        @register="app.register"
        @load-captcha="app.loadCaptcha"
        @offline="app.enterOfflineMode"
      />
    </section>
  </main>
</template>
