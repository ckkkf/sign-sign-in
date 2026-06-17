<script setup lang="ts">
import Button from "@kousum/semi-ui-vue/dist/button";
import Input from "@kousum/semi-ui-vue/dist/input";
import Modal from "@kousum/semi-ui-vue/dist/modal";
import Select from "@kousum/semi-ui-vue/dist/select";
import Space from "@kousum/semi-ui-vue/dist/space";
import Spin from "@kousum/semi-ui-vue/dist/spin";
import TextArea from "@kousum/semi-ui-vue/dist/input/textArea";
import Toast from "@kousum/semi-ui-vue/dist/toast";
import { IconCopy, IconRefresh, IconSend } from "@kousum/semi-icons-vue";
import { computed, nextTick, ref, watch } from "vue";
import type {
  WeeklyJournalBlogList,
  WeeklyJournalHistoryItem,
  WeeklyJournalInit,
  WeeklyJournalSubmitPayload,
  WeeklyJournalWeek,
  WeeklyJournalYear
} from "@shared/types";
import { ensureOk } from "../utils/api";
import { stringifyParam, trackClientEvent } from "../utils/analytics";
import { renderIcon } from "../utils/icons";

type ChatMessage = {
  id: string;
  role: "user" | "ai";
  content: string;
  pending?: boolean;
};

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{ (event: "close"): void }>();

const loading = ref(false);
const loadingWeeks = ref(false);
const generating = ref(false);
const submitting = ref(false);
const submitVisible = ref(false);
const detailVisible = ref(false);
const data = ref<WeeklyJournalInit | null>(null);
const inputText = ref("");
const messages = ref<ChatMessage[]>([]);
const submitContent = ref("");
const selectedYear = ref("");
const selectedMonth = ref("");
const selectedWeekKey = ref("");
const blogTitle = ref("实习周记");
const blogOpenType = ref("2");
const blogPage = ref(1);
const activeBlog = ref<any>(null);
const chatBody = ref<HTMLElement | null>(null);

const years = computed(() => data.value?.years || []);
const weeks = computed(() => data.value?.weeks || []);
const history = computed(() => data.value?.history || []);
const blogs = computed(() => data.value?.blogs);
const blogList = computed(() => blogItems(blogs.value));
const yearOptions = computed(() => years.value.map((item, index) => ({ value: String(index), label: `${item.year}年` })));
const monthOptions = computed(() => monthList(years.value[Number(selectedYear.value)]).map((month) => ({ value: String(month), label: `${month}月` })));
const weekOptions = computed(() =>
  weeks.value.map((week, index) => ({
    value: weekKey(week, index),
    label: weekLabel(week)
  }))
);
const selectedWeek = computed(() => weeks.value.find((week, index) => weekKey(week, index) === selectedWeekKey.value));

watch(
  () => props.visible,
  (visible) => {
    if (visible && !data.value) {
      window.setTimeout(() => void init(), 100);
    }
  }
);

function monthList(year?: WeeklyJournalYear): Array<string | number> {
  return (year?.monthList || [])
    .map((month: any) => {
      if (month && typeof month === "object") return month.id ?? month.month ?? month.value ?? month.label;
      return month;
    })
    .filter((month) => month !== undefined && month !== null)
    .sort((a, b) => Number(a) - Number(b));
}

function weekKey(week: WeeklyJournalWeek, index: number) {
  return `${week.startDate || ""}|${week.endDate || ""}|${index}`;
}

function weekLabel(week: WeeklyJournalWeek) {
  const weekNo = week.week || week.weekNum || week.weekNo || "";
  const status = week.isSubmit || week.submitted || week.blogCount ? "已提交" : "未提交";
  const count = week.blogCount !== undefined ? ` (${week.blogCount}篇)` : "";
  return `${weekNo ? `第${weekNo}周 ` : ""}(${week.startDate || "-"} ~ ${week.endDate || "-"}) - ${status}${count}`;
}

function pickDefaults(next: WeeklyJournalInit) {
  selectedYear.value = next.years[0] ? "0" : "";
  selectedMonth.value = String(monthList(next.years[0])[0] || "");
  selectedWeekKey.value = next.weeks[0] ? weekKey(next.weeks[0], 0) : "";
}

async function run<T>(action: () => Promise<T>, success?: string): Promise<T | undefined> {
  try {
    const result = await action();
    if (success) Toast.success(success);
    return result;
  } catch (error) {
    Toast.error(error instanceof Error ? error.message : String(error));
    return undefined;
  }
}

async function init() {
  loading.value = true;
  const startedAt = Date.now();
  try {
    await run(async () => {
      const next = ensureOk(await window.signSignIn.weeklyJournal.init());
      data.value = next;
      pickDefaults(next);
      trackClientEvent({
        operType: "WEEKLY_JOURNAL_OPEN",
        status: "0",
        title: "打开 AI 与周记",
        responseSummary: `history=${next.history?.length || 0}, blogs=${next.blogs?.items?.length || 0}`,
        costTime: Date.now() - startedAt
      });
    });
  } finally {
    loading.value = false;
  }
}

async function loadWeeks() {
  if (!data.value || !selectedYear.value || !selectedMonth.value || loadingWeeks.value) return;
  const year = years.value[Number(selectedYear.value)]?.year;
  if (!year) return;
  loadingWeeks.value = true;
  selectedWeekKey.value = "";
  try {
    await run(async () => {
      data.value!.weeks = ensureOk(await window.signSignIn.weeklyJournal.loadWeeks(String(year), selectedMonth.value));
      selectedWeekKey.value = data.value!.weeks[0] ? weekKey(data.value!.weeks[0], 0) : "";
    });
  } finally {
    loadingWeeks.value = false;
  }
}

async function loadBlogs(page = blogPage.value) {
  const startedAt = Date.now();
  await run(async () => {
    const next = ensureOk(await window.signSignIn.weeklyJournal.loadBlogs(page));
    blogPage.value = page;
    if (data.value) data.value.blogs = next;
    trackClientEvent({
      operType: "WEEKLY_JOURNAL_LOAD_BLOGS",
      status: "0",
      title: "刷新周记列表",
      requestParam: stringifyParam({ page }),
      responseSummary: `items=${next.items?.length || 0}`,
      costTime: Date.now() - startedAt
    });
  });
}

async function sendMessage() {
  const content = inputText.value.trim();
  if (!content || generating.value) return;
  const startedAt = Date.now();
  const userMessage: ChatMessage = { id: `${Date.now()}-user`, role: "user", content };
  const aiMessage: ChatMessage = { id: `${Date.now()}-ai`, role: "ai", content: "正在思考...", pending: true };
  messages.value.push(userMessage, aiMessage);
  inputText.value = "";
  generating.value = true;
  scrollToBottom();
  try {
    await run(async () => {
      const item = ensureOk(await window.signSignIn.weeklyJournal.generate(content));
      aiMessage.content = "";
      for (const char of item.content) {
        aiMessage.content += char;
        await new Promise((resolve) => window.setTimeout(resolve, 4));
      }
      aiMessage.pending = false;
      if (data.value) data.value.history = [item, ...data.value.history].slice(0, 50);
      trackClientEvent({
        operType: "WEEKLY_JOURNAL_GENERATE",
        status: "0",
        title: "AI 生成周记",
        requestParam: stringifyParam({ length: content.length }),
        responseSummary: `contentLength=${item.content?.length || 0}`,
        costTime: Date.now() - startedAt
      });
      scrollToBottom();
    });
  } finally {
    aiMessage.pending = false;
    generating.value = false;
  }
}

function scrollToBottom() {
  void nextTick(() => {
    if (chatBody.value) chatBody.value.scrollTop = chatBody.value.scrollHeight;
  });
}

function clearChat() {
  messages.value = [];
  trackClientEvent({
    operType: "WEEKLY_JOURNAL_NEW_CHAT",
    status: "0",
    title: "AI 周记新对话"
  });
}

function useHistory(item: WeeklyJournalHistoryItem) {
  messages.value.push({ id: `${Date.now()}-history`, role: "ai", content: item.content });
  scrollToBottom();
}

async function copyText(text: string) {
  await navigator.clipboard.writeText(text);
  Toast.success("已复制");
}

function openSubmit(content: string) {
  submitContent.value = content;
  blogOpenType.value = "2";
  const week = selectedWeek.value;
  const weekNo = week?.week || week?.weekNum || week?.weekNo || "";
  blogTitle.value = weekNo ? `第${weekNo}周实习周记` : "实习周记";
  submitVisible.value = true;
}

async function submit() {
  const week = selectedWeek.value;
  if (!data.value?.traineeId || !week?.startDate || !week?.endDate || !submitContent.value.trim()) {
    Toast.warning("请选择周次并填写周记内容");
    return;
  }
  submitting.value = true;
  const startedAt = Date.now();
  try {
    const payload: WeeklyJournalSubmitPayload = {
      blogTitle: blogTitle.value || "实习周记",
      blogBody: submitContent.value,
      blogOpenType: blogOpenType.value,
      traineeId: data.value.traineeId,
      startDate: week.startDate,
      endDate: week.endDate
    };
    await run(async () => {
      ensureOk(await window.signSignIn.weeklyJournal.submit(payload));
      submitVisible.value = false;
      await loadBlogs(1);
      trackClientEvent({
        operType: "WEEKLY_JOURNAL_SUBMIT",
        status: "0",
        title: "提交周记",
        requestParam: stringifyParam({ blogTitle: payload.blogTitle, startDate: payload.startDate, endDate: payload.endDate }),
        responseSummary: `contentLength=${payload.blogBody.length}`,
        costTime: Date.now() - startedAt
      });
    }, "周记提交成功");
  } finally {
    submitting.value = false;
  }
}

function blogItems(list?: WeeklyJournalBlogList): any[] {
  return list?.items || [];
}

function showBlog(blog: any) {
  activeBlog.value = blog;
  detailVisible.value = true;
}

function blogBody(blog: any) {
  return String(blog?.blogBody || blog?.content || blog?.summary || "");
}

function blogDate(blog: any) {
  const raw = String(blog?.commitDate || blog?.endDate || "");
  const match = raw.match(/\d{4}[.-](\d{1,2})[.-](\d{1,2})/);
  return match ? `${match[1]}.${match[2]}` : raw;
}
</script>

<template>
  <Modal className="compact-tool-modal weekly-modal" :visible="visible" :width="940" footer="" @cancel="emit('close')">
    <template #header>
      <div class="weekly-modal-titlebar">
        <div class="weekly-modal-title-copy">
          <strong>AI 与周记</strong>
          <span>输入要点后生成周记，可复制或提交到周记。</span>
        </div>
        <Button theme="borderless" size="small" :icon="renderIcon(IconRefresh)" @click="loadBlogs(1)" />
      </div>
    </template>
    <Spin :spinning="loading">
      <section class="journal-dialog chat-mode">
        <aside class="journal-side">
          <section class="journal-side-section">
            <div class="journal-side-title">
              <strong>生成历史</strong>
              <Button type="primary" size="small" @click="clearChat">新对话</Button>
            </div>
            <span class="journal-count">{{ history.length }} 条</span>
            <section class="journal-list">
              <button v-for="item in history" :key="item.id" class="journal-nav-item" type="button" @click="useHistory(item)">
                <strong>{{ new Date(item.createdAt).toLocaleString().slice(5, 16) }} · {{ item.content.slice(0, 18) }}...</strong>
                <span>{{ item.content }}</span>
              </button>
              <div v-if="!history.length" class="dialog-empty">暂无生成历史</div>
            </section>
          </section>

          <section class="journal-side-section submitted-section">
            <div class="journal-side-title">
              <strong>已提交</strong>
              <span>第 {{ blogPage }} 页</span>
            </div>
            <section class="journal-list submitted-list">
              <button v-for="blog in blogList" :key="blog.id || blog.blogId || JSON.stringify(blog).slice(0, 40)" class="journal-nav-item compact" type="button" @click="showBlog(blog)">
                <strong>{{ blog.blogTitle || blog.title || "无标题" }}</strong>
                <span>{{ blogDate(blog) }} · {{ blogBody(blog).slice(0, 36) }}</span>
              </button>
              <div v-if="!blogList.length" class="dialog-empty">暂无已提交周记</div>
            </section>
            <div class="journal-pager">
              <Button theme="light" size="small" :disabled="blogPage <= 1" @click="loadBlogs(Math.max(1, blogPage - 1))">上一页</Button>
              <Button theme="light" size="small" :disabled="!blogList.length" @click="loadBlogs(blogPage + 1)">下一页</Button>
            </div>
          </section>
        </aside>

        <section class="chat-panel">
          <header class="chat-panel-head">
            <Button theme="light" size="small" @click="clearChat">清空</Button>
          </header>
          <div ref="chatBody" class="chat-body">
            <div v-if="!messages.length" class="chat-empty">
              <strong>暂无对话</strong>
              <span>例如：本周完成了岗位培训、整理签到流程、协助处理日报。</span>
            </div>
            <article v-for="message in messages" :key="message.id" :class="['chat-message', message.role]">
              <span v-if="message.role === 'ai'" class="ai-mark">AI</span>
              <div class="chat-bubble">
                <p>{{ message.content }}</p>
                <div class="bubble-actions">
                  <Button theme="light" size="small" :icon="renderIcon(IconCopy)" @click="copyText(message.content)">复制</Button>
                  <Button v-if="message.role === 'ai' && !message.pending" theme="light" size="small" @click="openSubmit(message.content)">提交为周记</Button>
                </div>
              </div>
            </article>
          </div>
          <div class="chat-input-row">
            <TextArea
              :value="inputText"
              placeholder="输入本周工作、收获或需要改写的内容..."
              :autosize="{ minRows: 2, maxRows: 4 }"
              @change="(value: string) => (inputText = value)"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <Button type="primary" :loading="generating" :icon="renderIcon(IconSend)" @click="sendMessage">{{ generating ? "生成中..." : "发送" }}</Button>
          </div>
        </section>
      </section>
    </Spin>

    <Modal className="compact-tool-modal nested-tool-modal" :visible="submitVisible" title="提交周记配置" :width="560" footer="" @cancel="submitting ? undefined : (submitVisible = false)">
      <section class="journal-submit-modal">
        <Select :value="selectedYear" :disabled="loadingWeeks || submitting" :option-list="yearOptions" @change="(value: any) => { selectedYear = String(value); selectedMonth = String(monthOptions[0]?.value || ''); loadWeeks(); }" />
        <Select :value="selectedMonth" :disabled="loadingWeeks || submitting" :option-list="monthOptions" @change="(value: any) => { selectedMonth = String(value); loadWeeks(); }" />
        <Select :value="selectedWeekKey" :disabled="loadingWeeks || submitting" :option-list="weekOptions" placeholder="周次" @change="(value: any) => (selectedWeekKey = String(value))" />
        <Select
          :value="blogOpenType"
          :disabled="submitting"
          :option-list="[
            { value: '2', label: '仅老师可见' },
            { value: '0', label: '仅老师和同学可见' },
            { value: '1', label: '全网可见' }
          ]"
          @change="(value: any) => (blogOpenType = String(value))"
        />
        <Input :value="blogTitle" :disabled="submitting" placeholder="标题" @change="(value: string) => (blogTitle = value)" />
        <TextArea :value="submitContent" :disabled="submitting" :autosize="{ minRows: 8, maxRows: 12 }" @change="(value: string) => (submitContent = value)" />
        <Space>
          <Button type="primary" :loading="submitting" @click="submit">{{ submitting ? "提交中..." : "提交" }}</Button>
          <Button theme="light" :disabled="submitting" @click="submitVisible = false">取消</Button>
        </Space>
      </section>
    </Modal>

    <Modal className="compact-tool-modal nested-tool-modal" :visible="detailVisible" :title="activeBlog?.blogTitle || '周记详情'" :width="560" footer="" @cancel="detailVisible = false">
      <section class="journal-detail">
        <span>{{ blogDate(activeBlog) }} · {{ activeBlog?.startDate || "" }}-{{ activeBlog?.endDate || "" }}</span>
        <p>{{ blogBody(activeBlog) }}</p>
        <Space>
          <Button theme="light" :icon="renderIcon(IconCopy)" @click="copyText(blogBody(activeBlog))">复制内容</Button>
          <Button theme="light" @click="() => { messages.push({ id: `${Date.now()}-blog`, role: 'ai', content: blogBody(activeBlog) }); detailVisible = false; scrollToBottom(); }">编辑引用</Button>
        </Space>
      </section>
    </Modal>
  </Modal>
</template>
