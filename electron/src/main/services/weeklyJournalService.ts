import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { XYB_REFERER, XYB_VERSION } from "@shared/constants";
import type {
  SignConfig,
  WeeklyJournalBlogList,
  WeeklyJournalHistoryItem,
  WeeklyJournalInit,
  WeeklyJournalSubmitPayload,
  WeeklyJournalWeek,
  WeeklyJournalYear
} from "@shared/types";
import * as xybApi from "../api/xybClient";
import type { LoginArgs, XybResponse } from "../api/types/xybTypes";
import { http } from "../api/httpClient";
import { configStore } from "./configStore";
import { ensureParent, getUserRoot } from "./paths";
import { sessionStore } from "./sessionStore";
import { getDeviceCode, getHeaderToken } from "./xybToken";

function responseMessage(data: unknown): string {
  if (data && typeof data === "object") {
    const body = data as { msg?: unknown; message?: unknown };
    const msg = body.msg ?? body.message;
    if (msg !== undefined && msg !== null && String(msg).trim()) return String(msg);
  }
  return JSON.stringify(data);
}

function assertSession<T>(body: XybResponse<T>): void {
  if (body.code === "205" || body.code === 205 || String(body.msg || "").includes("未登录")) {
    sessionStore.clear();
    throw new Error("JSESSIONID已失效，请重新获取code");
  }
}

function extractItems(raw: any): any[] {
  if (Array.isArray(raw)) return raw;
  if (Array.isArray(raw?.list)) return raw.list;
  if (Array.isArray(raw?.rows)) return raw.rows;
  if (Array.isArray(raw?.data)) return raw.data;
  if (Array.isArray(raw?.records)) return raw.records;
  return [];
}

export class WeeklyJournalService {
  private historyPath = join(getUserRoot(), "cache", "journal_history.json");

  async init(): Promise<WeeklyJournalInit> {
    const { config, args } = await this.ensureLogin();
    const traineeId = await this.tryResolveTraineeId(config, args);
    const years = traineeId ? await this.loadYearsWithArgs(args, config) : [];
    const firstYear = years[0];
    const firstMonth = this.firstMonth(firstYear);
    const weeks = traineeId && firstYear && firstMonth ? await this.loadWeeksWithArgs(args, config, String(firstYear.year), String(firstMonth)) : [];
    const blogs = traineeId ? await this.loadBlogsWithArgs(args, config, 1) : { page: 1, raw: [], items: [] };
    return {
      traineeId,
      years,
      weeks,
      history: this.readHistory(),
      blogs
    };
  }

  async loadYears(): Promise<WeeklyJournalYear[]> {
    const { config, args } = await this.ensurePlan();
    return this.loadYearsWithArgs(args, config);
  }

  async loadWeeks(year: string, month: string): Promise<WeeklyJournalWeek[]> {
    const { config, args } = await this.ensurePlan();
    return this.loadWeeksWithArgs(args, config, year, month);
  }

  async loadBlogs(page: number): Promise<WeeklyJournalBlogList> {
    const { config, args } = await this.ensurePlan();
    return this.loadBlogsWithArgs(args, config, page);
  }

  async generate(prompt: string): Promise<WeeklyJournalHistoryItem> {
    const { config, args } = await this.ensureLogin();
    const content = await this.xybCompletion(args, config.input, this.normalizePrompt(prompt));
    const item: WeeklyJournalHistoryItem = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      prompt,
      content,
      createdAt: Date.now()
    };
    this.saveHistory([item, ...this.readHistory()].slice(0, 50));
    return item;
  }

  private normalizePrompt(prompt: string): string {
    const trimmed = String(prompt || "").trim();
    return (trimmed || "帮我生成一篇公司实习周记").slice(0, 500);
  }

  async submit(payload: WeeklyJournalSubmitPayload): Promise<any> {
    const { config, args } = await this.ensurePlan();
    const data = {
      blogType: "1",
      blogTitle: payload.blogTitle,
      blogBody: payload.blogBody,
      blogOpenType: String(payload.blogOpenType),
      traineeId: String(payload.traineeId || args.traineeId || ""),
      isDraft: "0",
      startDate: payload.startDate,
      endDate: payload.endDate,
      backgroundTemplateId: "0",
      fileJson: '[{"fileName":""}]',
      blogId: "undefined"
    };
    return this.formPost<any>("https://xcx.xybsyw.com/student/blog/Blog!save.action", data, args, config.input, true, "提交周记失败");
  }

  readHistory(): WeeklyJournalHistoryItem[] {
    if (!existsSync(this.historyPath)) return [];
    try {
      const history = JSON.parse(readFileSync(this.historyPath, "utf-8"));
      if (Array.isArray(history)) return history.slice(0, 50);
      if (Array.isArray(history?.generated)) {
        return history.generated.slice(0, 50).map((item: any, index: number) => ({
          id: `${item.timestamp || Date.now()}-${index}`,
          prompt: "",
          content: String(item.content || ""),
          createdAt: Date.parse(String(item.timestamp || "")) || Date.now()
        }));
      }
      return [];
    } catch {
      return [];
    }
  }

  private saveHistory(history: WeeklyJournalHistoryItem[]): void {
    ensureParent(this.historyPath);
    const payload = {
      generated: history.slice(0, 50).map((item) => ({
        timestamp: formatHistoryTime(new Date(item.createdAt)),
        content: item.content
      })),
      submitted: []
    };
    writeFileSync(this.historyPath, JSON.stringify(payload, null, 2), "utf-8");
  }

  private async ensureLogin(): Promise<{ config: SignConfig; args: LoginArgs }> {
    const config = configStore.read();
    const args = await xybApi.login(config.input, true);
    return { config, args };
  }

  private async tryResolveTraineeId(config: SignConfig, args: LoginArgs): Promise<string> {
    try {
      const plan = await xybApi.getPlan(config.input, args);
      const traineeId = String(plan?.[0]?.dateList?.[0]?.traineeId || args.traineeId || "");
      if (traineeId && !args.traineeId) {
        sessionStore.save({ ...args, traineeId });
        args.traineeId = traineeId;
      }
      return traineeId;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes("列表为空") || message.includes("未获取到 traineeId")) {
        return "";
      }
      throw error;
    }
  }

  private async ensurePlan(): Promise<{ config: SignConfig; args: LoginArgs; traineeId: string }> {
    const { config, args } = await this.ensureLogin();
    const plan = await xybApi.getPlan(config.input, args);
    const traineeId = String(plan?.[0]?.dateList?.[0]?.traineeId || args.traineeId || "");
    if (!traineeId) throw new Error("未获取到 traineeId，无法加载或提交周记；AI 生成仍可直接使用");
    if (!args.traineeId) {
      sessionStore.save({ ...args, traineeId });
      args.traineeId = traineeId;
    }
    return { config, args, traineeId };
  }

  private firstMonth(year?: WeeklyJournalYear): string | number | undefined {
    const first = year?.monthList?.[0];
    if (first && typeof first === "object") {
      return first.month ?? first.value ?? first.label;
    }
    return first as string | number | undefined;
  }

  private async loadYearsWithArgs(args: LoginArgs, config: SignConfig): Promise<WeeklyJournalYear[]> {
    const data = { traineeId: String(args.traineeId || "") };
    const raw = await this.formPost<any>(
      "https://xcx.xybsyw.com/student/blog/LoadBlogDate!weekYear.action",
      data,
      args,
      config.input,
      false,
      "加载年份月份失败"
    );
    return Array.isArray(raw) ? raw : [];
  }

  private async loadWeeksWithArgs(args: LoginArgs, config: SignConfig, year: string, month: string): Promise<WeeklyJournalWeek[]> {
    const data = {
      year: String(year),
      month: String(month),
      traineeId: String(args.traineeId || ""),
      id: ""
    };
    const raw = await this.formPost<any>(
      "https://xcx.xybsyw.com/student/blog/LoadBlogDate!week.action",
      data,
      args,
      config.input,
      false,
      "加载周信息失败"
    );
    return Array.isArray(raw) ? raw : [];
  }

  private async loadBlogsWithArgs(args: LoginArgs, config: SignConfig, page: number): Promise<WeeklyJournalBlogList> {
    const raw = await this.formPost<any>(
      "https://xcx.xybsyw.com/student/blog/BlogList.action",
      {
        blogType: "1",
        planId: "",
        reviewStatus: "null",
        page: String(page)
      },
      args,
      config.input,
      true,
      "获取周记列表失败"
    );
    return { page, raw, items: extractItems(raw) };
  }

  private async xybCompletion(args: LoginArgs, input: SignConfig["input"], prompt: string): Promise<string> {
    const raw = await this.formPost<any>(
      "https://xcx.xybsyw.com/careerplanning/saveSession.action",
      {
        processType: "0",
        content: prompt,
        questionType: "0",
        type: "0",
        aiSessionMsgType: "4"
      },
      args,
      input,
      true,
      "AI生成失败",
      60000
    );
    const content = String(raw?.content || "");
    if (!content) throw new Error("AI生成失败：接口未返回内容");
    return content;
  }

  private async formPost<T>(
    url: string,
    data: Record<string, string>,
    args: LoginArgs,
    input: SignConfig["input"],
    includeDeviceCode: boolean,
    context: string,
    timeout = 10000
  ): Promise<T> {
    const token = getHeaderToken(data);
    const response = await http.post(url, new URLSearchParams(data), {
      timeout,
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        encryptvalue: args.encryptValue,
        m: token.m,
        n: token.n,
        referer: XYB_REFERER,
        s: token.s,
        t: token.t,
        "user-agent": input.userAgent,
        v: XYB_VERSION,
        wechat: "1",
        xweb_xhr: "1",
        ...(includeDeviceCode ? { devicecode: getDeviceCode(args.openId, input.device) } : {}),
        Cookie: `JSESSIONID=${args.sessionId}`
      }
    });
    const body = response.data as XybResponse<T>;
    assertSession(body);
    if (!(body.code === "200" || body.code === 200) || body.data === undefined) {
      throw new Error(`${context}: ${responseMessage(body)}`);
    }
    return body.data;
  }
}

function formatHistoryTime(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export const weeklyJournalService = new WeeklyJournalService();
