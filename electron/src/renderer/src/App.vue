<script setup lang="ts">
import Layout from "@kousum/semi-ui-vue/dist/layout";
import AppRail from "./components/AppRail.vue";
import AutoClockDialog from "./components/AutoClockDialog.vue";
import FeedbackDialog from "./components/FeedbackDialog.vue";
import ImageManagerDialog from "./components/ImageManagerDialog.vue";
import LoginDialog from "./components/LoginDialog.vue";
import LogPanel from "./components/LogPanel.vue";
import NoticeBanner from "./components/NoticeBanner.vue";
import UpdateCenterDialog from "./components/UpdateCenterDialog.vue";
import WeeklyJournalDialog from "./components/WeeklyJournalDialog.vue";
import { useAppState } from "./composables/useAppState";
import ConfigPage from "./pages/ConfigPage.vue";
import DashboardPage from "./pages/DashboardPage.vue";
import JieLongPage from "./pages/JieLongPage.vue";

const app = useAppState();
</script>

<template>
  <div class="app-shell">
    <Layout>
      <Layout.Sider :style="{ width: '56px' }" class="app-sider">
      <AppRail
        :page="app.page.value"
        :user="app.authState.value.user"
        :offline="app.offlineMode.value"
        @change-page="(nextPage) => (app.page.value = nextPage)"
        @open-login="app.openLoginIfLoggedOut"
        @logout="app.logout"
      />
    </Layout.Sider>

    <section class="workspace">
      <div class="banner-stack">
        <NoticeBanner :boot-error="app.bootError.value" :notice-content="app.noticeContent.value" />
      </div>

      <section class="workspace-body" :style="{ '--log-panel-width': `${app.logPanelWidth.value}px` }">
          <section class="main-panel">
            <button v-if="app.offlineMode.value" class="offline-banner" type="button" @click="app.openLoginIfLoggedOut">离线模式</button>
            <div class="main-content-pad">
              <DashboardPage
                v-if="app.page.value === 'dashboard'"
                :action-options="app.actionOptions"
                :auto-clock="app.autoClock.value"
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
                @open-image-manager="app.openImageManager"
                @open-feedback="app.openFeedback"
                @open-cert-manager="app.openCertManager"
                @open-config-file="app.openConfigFile"
                @open-external="app.openExternal"
                @open-terminal="app.openTerminal"
                @open-update-center="app.openUpdateCenter"
                @open-auto-clock="app.openAutoClockDialog"
                @open-weekly-journal="app.openWeeklyJournal"
                @open-proxy-settings="app.openProxySettings"
                @open-user-data-dir="app.openUserDataDir"
                @flush-dns="app.flushDns"
                @refresh-all="app.manualRefreshAll"
                @start-capture="app.startCapture"
                @start-task="app.startTask"
                @stop-capture="app.stopCapture"
                @stop-task="app.stopTask"
                @toggle-auto-clock="app.toggleAutoClock"
              />

              <JieLongPage
                v-else-if="app.page.value === 'jielong'"
                :images="app.images.value"
                @open-image-manager="app.openImageManager"
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

      <LoginDialog
        :visible="app.loginVisible.value"
        :loading="app.loginLoading.value"
        :register-loading="app.registerLoading.value"
        :captcha-loading="app.captchaLoading.value"
        :login-captcha-loading="app.loginCaptchaLoading.value"
        :email-code-loading="app.emailCodeLoading.value"
        :email-uuid="app.registerEmailUuid.value"
        :register-success-tick="app.registerSuccessTick.value"
        :captcha="app.authCaptcha.value"
        :login-captcha="app.loginAuthCaptcha.value"
        @login="app.login"
        @register="app.register"
        @load-captcha="app.loadCaptcha"
        @load-login-captcha="app.loadLoginCaptcha"
        @send-email-code="app.sendEmailCode"
        @clear-email-code="app.clearRegisterEmailCode"
        @offline="app.enterOfflineMode"
      />

      <FeedbackDialog
        :visible="app.feedbackVisible.value"
        :loading="app.feedbackLoading.value"
        @close="app.feedbackVisible.value = false"
        @submit="app.submitFeedback"
      />

      <ImageManagerDialog
        :visible="app.imageManagerVisible.value"
        :images="app.images.value"
        :selected-image="app.selectedImage.value"
        @close="app.imageManagerVisible.value = false"
        @select="(path) => (app.selectedImage.value = path)"
        @import="app.importImage"
        @rename="app.renameImage"
        @replace="app.replaceImage"
        @delete="app.deleteImage"
        @refresh="app.refreshAll"
        @open-dir="app.openImageDir"
      />

      <UpdateCenterDialog
        :visible="app.updateCenterVisible.value"
        @close="app.updateCenterVisible.value = false"
      />

      <AutoClockDialog
        :visible="app.autoClockDialogVisible.value"
        :auto-clock="app.autoClock.value"
        :draft="app.draft"
        @close="app.autoClockDialogVisible.value = false"
        @change-input="app.changeInput"
        @update-tasks="(tasks) => (app.draft.autoClockTasks = tasks)"
        @update-notifications="(notifications) => (app.draft.notifications = notifications)"
        @import-image-for-task="app.importImageForTask"
        @test-notification="app.testNotification"
        @save-config="app.saveConfig"
        @toggle-auto-clock="app.toggleAutoClock"
      />

      <WeeklyJournalDialog
        :visible="app.weeklyJournalVisible.value"
        @close="app.weeklyJournalVisible.value = false"
      />
    </section>
  </Layout>
</div>
</template>
