export function ensureOk<T>(result: { ok: boolean; data?: T; error?: string }): T {
  if (!result.ok) throw new Error(result.error || "操作失败");
  return result.data as T;
}
