<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Select from "@kousum/semi-ui-vue/dist/select";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import { reactive } from "vue";
import type { FeedbackPayload } from "../services/authApi";

defineProps<{
  visible: boolean;
  loading: boolean;
}>();

const emit = defineEmits<{
  (event: "close"): void;
  (event: "submit", payload: FeedbackPayload): void;
}>();

const form = reactive<FeedbackPayload>({
  title: "",
  feedbackType: "功能建议",
  priority: "1",
  contact: "",
  content: ""
});

/** 提交反馈表单。 */
function submit() {
  emit("submit", {
    title: form.title.trim(),
    feedbackType: form.feedbackType,
    priority: form.priority,
    contact: form.contact.trim(),
    content: form.content.trim()
  });
}

/** 更新反馈类型。 */
function changeFeedbackType(value: string | number | any[] | Record<string, any> | undefined) {
  form.feedbackType = String(value || "功能建议");
}

/** 更新反馈优先级。 */
function changePriority(value: string | number | any[] | Record<string, any> | undefined) {
  form.priority = String(value || "1");
}
</script>

<template>
  <Teleport to="body">
    <Transition name="login-fade">
      <div v-if="visible" class="dialog-overlay" role="presentation">
        <section class="feedback-panel" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
          <header class="feedback-head">
            <div>
              <h2 id="feedback-title">发送反馈</h2>
              <p>请描述问题、重现步骤或期望改进，我们会尽快处理。</p>
            </div>
            <button class="dialog-close" type="button" :disabled="loading" @click="emit('close')">×</button>
          </header>

          <div class="feedback-form">
            <label class="login-field">
              <span>标题</span>
              <Input
                :value="form.title"
                placeholder="一句话说明反馈主题"
                :disabled="loading"
                @change="(value: string) => (form.title = value)"
              />
            </label>

            <div class="feedback-row">
              <label class="login-field">
                <span>反馈类型</span>
                <Select
                  :value="form.feedbackType"
                  :disabled="loading"
                  @change="changeFeedbackType"
                >
                  <Select.Option value="功能建议">功能建议</Select.Option>
                  <Select.Option value="Bug 反馈">Bug 反馈</Select.Option>
                  <Select.Option value="使用咨询">使用咨询</Select.Option>
                  <Select.Option value="其他问题">其他问题</Select.Option>
                </Select>
              </label>

              <label class="login-field">
                <span>优先级</span>
                <Select
                  :value="form.priority"
                  :disabled="loading"
                  @change="changePriority"
                >
                  <Select.Option value="0">低</Select.Option>
                  <Select.Option value="1">中</Select.Option>
                  <Select.Option value="2">高</Select.Option>
                </Select>
              </label>
            </div>

            <label class="login-field">
              <span>联系方式</span>
              <Input
                :value="form.contact"
                placeholder="Email / QQ / 微信（可选）"
                :disabled="loading"
                @change="(value: string) => (form.contact = value)"
              />
            </label>

            <label class="login-field">
              <span>反馈内容</span>
              <TextArea
                :value="form.content"
                placeholder="请尽量描述清楚问题、重现步骤或你期待的功能..."
                :autosize="{ minRows: 5, maxRows: 8 }"
                :disabled="loading"
                @change="(value: string) => (form.content = value)"
              />
            </label>
          </div>

          <footer class="feedback-actions">
            <Button theme="borderless" type="tertiary" :disabled="loading" @click="emit('close')">取消</Button>
            <Button theme="solid" type="primary" :loading="loading" @click="submit">提交反馈</Button>
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>
