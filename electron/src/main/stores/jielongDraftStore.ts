import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import type { JieLongFieldAnswer } from "@shared/types";
import { ensureDir, ensureParent, getRuntimeJieLongDraftsPath } from "../services/paths";

type DraftStore = Record<string, { answers?: Record<string, JieLongFieldAnswer> }>;

class JieLongDraftStore {
  get(threadId: string): Record<string, JieLongFieldAnswer> {
    const drafts = this.read();
    return structuredClone(drafts[String(threadId || "").trim()]?.answers || {});
  }

  save(threadId: string, answers: Record<string, JieLongFieldAnswer>): boolean {
    const key = String(threadId || "").trim();
    if (!key) return false;
    const drafts = this.read();
    drafts[key] = { answers: structuredClone(answers || {}) };
    this.write(drafts);
    return true;
  }

  private read(): DraftStore {
    const path = getRuntimeJieLongDraftsPath();
    if (!existsSync(path)) return {};
    try {
      return JSON.parse(readFileSync(path, "utf-8")) as DraftStore;
    } catch {
      return {};
    }
  }

  private write(drafts: DraftStore): void {
    const path = getRuntimeJieLongDraftsPath();
    ensureDir(dirname(path));
    ensureParent(path);
    writeFileSync(path, JSON.stringify(drafts, null, 2), "utf-8");
  }
}

export const jielongDraftStore = new JieLongDraftStore();
