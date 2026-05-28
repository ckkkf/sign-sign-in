<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Space from "@kousum/semi-ui-vue/dist/space";
import Tabs from "@kousum/semi-ui-vue/dist/tabs";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import { IconKey, IconMail, IconUser, IconVerify } from "@kousum/semi-icons-vue";
import { computed, onUnmounted, reactive, ref, watch, type VNode } from "vue";
import type { AuthCaptcha, LoginPayload, RegisterPayload } from "@shared/types";
import logoUrl from "../assets/lingdong-logo.png";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  visible: boolean; loading: boolean; registerLoading: boolean;
  captchaLoading: boolean; loginCaptchaLoading: boolean; emailCodeLoading: boolean;
  emailUuid: string; registerSuccessTick: number;
  captcha: AuthCaptcha | null; loginCaptcha: AuthCaptcha | null;
}>();

const emit = defineEmits<{
  (e: "login", p: LoginPayload): void; (e: "register", p: RegisterPayload): void;
  (e: "loadCaptcha"): void; (e: "loadLoginCaptcha"): void; (e: "sendEmailCode", email: string): void;
  (e: "clearEmailCode"): void; (e: "offline"): void;
}>();

const mode = ref<"login" | "register">("login");
const form = reactive({ username: "", password: "", confirmPassword: "", email: "", emailCode: "", code: "", loginCode: "" });
const authTabs = [
  { tab: "登录", itemKey: "login" },
  { tab: "注册", itemKey: "register" }
];
const emptyFooter = () => "" as unknown as VNode;
const emailCodeCountdown = ref(0);
let emailCodeTimer: ReturnType<typeof setInterval> | null = null;

const emailCodeButtonText = computed(() => (emailCodeCountdown.value > 0 ? `${emailCodeCountdown.value}s 后重发` : "发送验证码"));

watch(() => props.visible, (v) => { if (v) mode.value = "login"; });
watch(mode, (n) => { if (n === "register" && !props.captcha) emit("loadCaptcha"); });
watch(() => props.registerSuccessTick, (tick) => { if (tick > 0) mode.value = "login"; });
watch(() => props.emailUuid, (uuid) => {
  if (uuid) {
    startEmailCodeCountdown();
  } else {
    stopEmailCodeCountdown();
  }
});

onUnmounted(stopEmailCodeCountdown);

function startEmailCodeCountdown() {
  stopEmailCodeCountdown();
  emailCodeCountdown.value = 60;
  emailCodeTimer = setInterval(() => {
    emailCodeCountdown.value -= 1;
    if (emailCodeCountdown.value <= 0) stopEmailCodeCountdown();
  }, 1000);
}

function stopEmailCodeCountdown() {
  if (emailCodeTimer) {
    clearInterval(emailCodeTimer);
    emailCodeTimer = null;
  }
  emailCodeCountdown.value = 0;
}

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function validateLogin() {
  if (!form.username.trim()) return "请输入账号";
  if (!form.password) return "请输入密码";
  if (!form.loginCode.trim()) return "请输入图形验证码";
  return "";
}

function validateRegister() {
  const loginError = validateLogin();
  if (loginError) return loginError;
  if (!form.confirmPassword) return "请再次输入密码";
  if (form.password !== form.confirmPassword) return "两次输入的密码不一致";
  if (!form.email.trim()) return "请输入邮箱";
  if (!isValidEmail(form.email.trim())) return "请输入正确的邮箱";
  if (!form.emailCode.trim()) return "请输入邮箱验证码";
  if (!form.code.trim()) return "请输入图形码";
  return "";
}

function sendEmailCode() {
  if (emailCodeCountdown.value > 0) return;

  const email = form.email.trim();
  if (!email) {
    Toast.warning("请先输入邮箱");
    return;
  }
  if (!isValidEmail(email)) {
    Toast.warning("请输入正确的邮箱");
    return;
  }
  emit("sendEmailCode", email);
}

function submit() {
  const error = mode.value === "register" ? validateRegister() : validateLogin();
  if (error) {
    Toast.warning(error);
    return;
  }

  if (mode.value === "register")
    emit("register", { username: form.username, password: form.password, confirmPassword: form.confirmPassword, email: form.email, emailCode: form.emailCode, emailUuid: props.emailUuid, code: form.code, uuid: props.captcha?.uuid || "" });
  else
    emit("login", { username: form.username, password: form.password, code: form.loginCode, uuid: props.loginCaptcha?.uuid || "" });
}
</script>

<template>
  <Modal class-name="login-modal" :visible="visible" :mask-closable="false" :width="400" :footer="emptyFooter" @cancel="emit('offline')">
    <Space vertical align="start" spacing="medium" class-name="login-dialog-stack">
      <Space align="center" spacing="medium">
        <div class="login-mark"><img :src="logoUrl" alt="SignSignIn" /></div>
        <Space vertical align="start" spacing="tight">
          <TypographyTitle :heading="5" class-name="login-title">{{ mode === "login" ? "Sign Sign In" : "注册账号" }}</TypographyTitle>
          <TypographyText type="tertiary">{{ mode === "login" ? "登录校友邦客户端账号后继续使用" : "创建校友邦客户端账号后即可登录" }}</TypographyText>
        </Space>
      </Space>

      <Tabs
        size="small"
        class-name="login-mode-tabs"
        :active-key="mode"
        :tab-list="authTabs"
        @change="(key: string) => mode = key as 'login' | 'register'"
      />

      <Space vertical spacing="medium" class-name="login-form-stack">
        <Input :value="form.username" placeholder="请输入账号" :inset-label="'账号'" :prefix="renderIcon(IconUser)" :disabled="loading" @change="(v: string) => form.username = v" @enter-press="submit" />
        <Input :value="form.password" mode="password" placeholder="请输入密码" :inset-label="'密码'" :prefix="renderIcon(IconKey)" :disabled="loading || registerLoading" @change="(v: string) => form.password = v" @enter-press="submit" />
        <template v-if="mode === 'login'">
          <Space align="center" spacing="tight" class-name="login-inline-control">
            <Input :value="form.loginCode" placeholder="请输入验证码" :inset-label="'验证码'" :prefix="renderIcon(IconVerify)" :disabled="loading" @change="(v: string) => form.loginCode = v" @enter-press="submit" />
            <Button theme="light" class-name="captcha-button" :loading="loginCaptchaLoading" @click="emit('loadLoginCaptcha')">
              <img v-if="loginCaptcha?.img" :src="loginCaptcha.img" alt="验证码" />
              <span v-else>刷新</span>
            </Button>
          </Space>
        </template>
        <template v-if="mode === 'register'">
          <Input :value="form.confirmPassword" mode="password" placeholder="请再次输入密码" :inset-label="'确认密码'" :prefix="renderIcon(IconKey)" :disabled="registerLoading" @change="(v: string) => form.confirmPassword = v" @enter-press="submit" />
          <Input :value="form.email" placeholder="请输入邮箱" :inset-label="'邮箱'" :prefix="renderIcon(IconMail)" :disabled="registerLoading" @change="(v: string) => { form.email = v; emit('clearEmailCode'); }" @enter-press="sendEmailCode" />
          <Space align="center" spacing="tight" class-name="login-inline-control">
            <Input :value="form.emailCode" placeholder="请输入邮箱验证码" :inset-label="'验证码'" :prefix="renderIcon(IconVerify)" :disabled="registerLoading" @change="(v: string) => form.emailCode = v" @enter-press="submit" />
            <Button theme="light" :loading="emailCodeLoading" :disabled="registerLoading || emailCodeCountdown > 0" @click="sendEmailCode">{{ emailCodeButtonText }}</Button>
          </Space>
          <Space align="center" spacing="tight" class-name="login-inline-control">
            <Input :value="form.code" placeholder="请输入验证码" :inset-label="'图形码'" :prefix="renderIcon(IconVerify)" :disabled="registerLoading" @change="(v: string) => form.code = v" @enter-press="submit" />
            <Button theme="light" class-name="captcha-button" :loading="captchaLoading" @click="emit('loadCaptcha')">
              <img v-if="captcha?.img" :src="captcha.img" alt="验证码" />
              <span v-else>刷新</span>
            </Button>
          </Space>
        </template>
      </Space>

      <Space vertical align="center" spacing="tight" class-name="login-action-stack">
        <Button block type="primary" :loading="mode === 'login' ? loading : registerLoading" @click="submit">{{ mode === "login" ? "登录" : "注册" }}</Button>
        <Button v-if="mode === 'login'" theme="borderless" type="tertiary" :disabled="loading" @click="emit('offline')">离线模式</Button>
        <Button v-else theme="borderless" type="tertiary" :disabled="registerLoading" @click="mode = 'login'">返回登录</Button>
      </Space>
    </Space>
  </Modal>
</template>
