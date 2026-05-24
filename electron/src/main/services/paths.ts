import { app } from "electron";
import { existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const moduleDir = dirname(fileURLToPath(import.meta.url));

export function getProjectRoot(): string {
  if (app.isPackaged) {
    return dirname(app.getPath("exe"));
  }
  return resolve(moduleDir, "../../..");
}

export function getUserRoot(): string {
  return app.getPath("userData");
}

export function getDefaultConfigPath(): string {
  return join(getProjectRoot(), "..", "resources", "config", "config.json");
}

export function getRuntimeConfigPath(): string {
  return join(getUserRoot(), "config", "config.json");
}

export function getRuntimeSessionPath(): string {
  return join(getUserRoot(), "cache", "session_cache.json");
}

export function getRuntimeAuthPath(): string {
  return join(getUserRoot(), "cache", "auth_cache.json");
}

export function getRuntimeImageDir(): string {
  return join(getUserRoot(), "img");
}

export function getRuntimeCertDir(): string {
  return join(getUserRoot(), "cert");
}

export function getRuntimeCertPath(): string {
  return join(getRuntimeCertDir(), "signsignin-node-proxy-ca.pem");
}

export function getRuntimeCertKeyPath(): string {
  return join(getRuntimeCertDir(), "signsignin-node-proxy-ca-key.pem");
}

export function getLegacyMitmCaPath(): string {
  return join(getLegacyMitmConfDir(), "mitmproxy-ca.pem");
}

export function getLegacyMitmCaCertPath(): string {
  return join(getLegacyMitmConfDir(), "mitmproxy-ca-cert.pem");
}

export function getLegacyMitmCaCerPath(): string {
  return join(getLegacyMitmConfDir(), "mitmproxy-ca-cert.cer");
}

export function getLegacyMitmConfDir(): string {
  return join(getUserRoot(), "..", "SignSignIn", "mitm", "conf");
}

export function getRuntimeLegacyMitmCaCertPath(): string {
  return join(getRuntimeCertDir(), "mitmproxy-ca-cert.pem");
}

export function ensureDir(path: string): void {
  if (!existsSync(path)) {
    mkdirSync(path, { recursive: true });
  }
}

export function ensureParent(path: string): void {
  ensureDir(dirname(path));
}
