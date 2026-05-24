<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import { IconKey, IconUser, IconVerify } from "@kousum/semi-icons-vue";
import { reactive, ref, watch } from "vue";
import type { AuthCaptcha, LoginPayload, RegisterPayload } from "@shared/types";
import logoUrl from "../assets/lingdong-logo.png";
import { renderIcon } from "../utils/icons";

const props = defineProps<{
  visible: boolean;
  loading: boolean;
  registerLoading: boolean;
  captchaLoading: boolean;
  captcha: AuthCaptcha | null;
}>();

const emit = defineEmits<{
  (event: "login", payload: LoginPayload): void;
  (event: "register", payload: RegisterPayload): void;
  (event: "loadCaptcha"): void;
  (event: "offline"): void;
}>();

const mode = ref<"login" | "register">("login");
const form = reactive({
  username: "",
  password: "",
  confirmPassword: "",
  code: ""
});

watch(
  () => props.visible,
  (visible) => {
    if (visible) mode.value = "login";
  }
);

watch(mode, (next) => {
  if (next === "register" && !props.captcha) {
    emit("loadCaptcha");
  }
});

function submit() {
  if (mode.value === "register") {
    emit("register", {
      username: form.username,
      password: form.password,
      confirmPassword: form.confirmPassword,
      code: form.code,
      uuid: props.captcha?.uuid || ""
    });
    return;
  }
  emit("login", {
    username: form.username,
    password: form.password
  });
}

function switchMode(next: "login" | "register") {
  mode.value = next;
}
</script>

<template>
  <Teleport to="body">
    <Transition name="login-fade">
      <div v-if="visible" class="login-overlay" role="presentation">
        <section class="login-panel" role="dialog" aria-modal="true" aria-labelledby="login-title">
          <header class="login-head">
            <div class="login-mark">
              <img :src="logoUrl" alt="SignSignIn" />
            </div>
            <div class="login-copy">
              <h2 id="login-title">{{ mode === "login" ? "SignSignIn" : "注册账号" }}</h2>
              <p>{{ mode === "login" ? "登录校友邦客户端账号后继续使用" : "创建校友邦客户端账号后即可登录" }}</p>
            </div>
          </header>

          <div class="auth-tabs" role="tablist">
            <button :class="{ 'is-active': mode === 'login' }" type="button" @click="switchMode('login')">登录</button>
            <button :class="{ 'is-active': mode === 'register' }" type="button" @click="switchMode('register')">注册</button>
          </div>

          <div class="login-form">
            <label class="login-field">
              <span>账号</span>
              <Input
                :value="form.username"
                size="large"
                placeholder="请输入账号"
                :prefix="renderIcon(IconUser)"
                :disabled="loading"
                @change="(value: string) => (form.username = value)"
                @enter-press="submit"
              />
            </label>
            <label class="login-field">
              <span>密码</span>
              <Input
                :value="form.password"
                mode="password"
                size="large"
                placeholder="请输入密码"
                :prefix="renderIcon(IconKey)"
                :disabled="loading || registerLoading"
                @change="(value: string) => (form.password = value)"
                @enter-press="submit"
              />
            </label>
            <label v-if="mode === 'register'" class="login-field">
              <span>确认密码</span>
              <Input
                :value="form.confirmPassword"
                mode="password"
                size="large"
                placeholder="请再次输入密码"
                :prefix="renderIcon(IconKey)"
                :disabled="registerLoading"
                @change="(value: string) => (form.confirmPassword = value)"
                @enter-press="submit"
              />
            </label>
            <label v-if="mode === 'register'" class="login-field">
              <span>验证码</span>
              <div class="captcha-row">
                <Input
                  :value="form.code"
                  size="large"
                  placeholder="请输入验证码"
                  :prefix="renderIcon(IconVerify)"
                  :disabled="registerLoading"
                  @change="(value: string) => (form.code = value)"
                  @enter-press="submit"
                />
                <button class="captcha-image" type="button" :disabled="captchaLoading" @click="emit('loadCaptcha')">
                  <img v-if="captcha?.img" :src="captcha.img" alt="验证码" />
                  <span v-else>{{ captchaLoading ? "加载中" : "刷新" }}</span>
                </button>
              </div>
            </label>
          </div>

          <footer class="login-actions">
            <Button
              class-name="login-submit"
              type="primary"
              :loading="mode === 'login' ? loading : registerLoading"
              @click="submit"
            >
              {{ mode === "login" ? "登录" : "注册" }}
            </Button>
            <button v-if="mode === 'login'" class="offline-link" type="button" :disabled="loading" @click="emit('offline')">离线模式</button>
            <button v-else class="offline-link" type="button" :disabled="registerLoading" @click="switchMode('login')">返回登录</button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
