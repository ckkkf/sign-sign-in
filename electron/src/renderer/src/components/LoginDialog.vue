<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Space from "@kousum/semi-ui-vue/dist/space";
import Tabs from "@kousum/semi-ui-vue/dist/tabs";
import TypographyText from "@kousum/semi-ui-vue/dist/typography/text";
import TypographyTitle from "@kousum/semi-ui-vue/dist/typography/title";
import { IconKey, IconMail, IconUser, IconVerify } from "@kousum/semi-icons-vue";
import { reactive, ref, watch, type VNode } from "vue";
import type { AuthCaptcha, LoginPayload, RegisterPayload } from "@shared/types";
import logoUrl from "../assets/lingdong-logo.png";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  visible: boolean; loading: boolean; registerLoading: boolean;
  captchaLoading: boolean; emailCodeLoading: boolean;
  emailUuid: string; captcha: AuthCaptcha | null;
}>();

const emit = defineEmits<{
  (e: "login", p: LoginPayload): void; (e: "register", p: RegisterPayload): void;
  (e: "loadCaptcha"): void; (e: "sendEmailCode", email: string): void;
  (e: "clearEmailCode"): void; (e: "offline"): void;
}>();

const mode = ref<"login" | "register">("login");
const form = reactive({ username: "", password: "", confirmPassword: "", email: "", emailCode: "", code: "" });
const authTabs = [
  { tab: "登录", itemKey: "login" },
  { tab: "注册", itemKey: "register" }
];
const emptyFooter = () => "" as unknown as VNode;

watch(() => props.visible, (v) => { if (v) mode.value = "login"; });
watch(mode, (n) => { if (n === "register" && !props.captcha) emit("loadCaptcha"); });

function submit() {
  if (mode.value === "register")
    emit("register", { username: form.username, password: form.password, confirmPassword: form.confirmPassword, email: form.email, emailCode: form.emailCode, emailUuid: props.emailUuid, code: form.code, uuid: props.captcha?.uuid || "" });
  else
    emit("login", { username: form.username, password: form.password });
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
        <template v-if="mode === 'register'">
          <Input :value="form.confirmPassword" mode="password" placeholder="请再次输入密码" :inset-label="'确认密码'" :prefix="renderIcon(IconKey)" :disabled="registerLoading" @change="(v: string) => form.confirmPassword = v" @enter-press="submit" />
          <Input :value="form.email" placeholder="请输入邮箱" :inset-label="'邮箱'" :prefix="renderIcon(IconMail)" :disabled="registerLoading" @change="(v: string) => { form.email = v; emit('clearEmailCode'); }" @enter-press="() => emit('sendEmailCode', form.email)" />
          <Space align="center" spacing="tight" class-name="login-inline-control">
            <Input :value="form.emailCode" placeholder="请输入邮箱验证码" :inset-label="'验证码'" :prefix="renderIcon(IconVerify)" :disabled="registerLoading" @change="(v: string) => form.emailCode = v" @enter-press="submit" />
            <Button theme="light" :loading="emailCodeLoading" :disabled="registerLoading" @click="() => emit('sendEmailCode', form.email)">发送验证码</Button>
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
