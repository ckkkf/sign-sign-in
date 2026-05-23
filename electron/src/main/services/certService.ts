import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { exec, execFile } from "node:child_process";
import { createRequire } from "node:module";
import { homedir } from "node:os";
import { promisify } from "node:util";
import type { pki as ForgePki, md as ForgeMd } from "node-forge";
import {
  ensureDir,
  getLegacyMitmCaPath,
  getRuntimeCertDir,
  getRuntimeCertKeyPath,
  getRuntimeCertPath,
  getRuntimeLegacyMitmCaCertPath
} from "./paths";
import { isMacos, isWindows, openCertManager } from "./systemService";
import { logger } from "./logger";

type ForgeModule = {
  pki: typeof ForgePki;
  md: typeof ForgeMd;
  asn1: {
    toDer(value: unknown): { getBytes(): string };
  };
};

type CertificateBundle = {
  certPem: string;
  keyPem: string;
  certPath: string;
  trustCertPath: string;
  commonName: string;
};

const require = createRequire(import.meta.url);
const forge = require("node-forge") as ForgeModule;
const execAsync = promisify(exec);
const execFileAsync = promisify(execFile);

export class CertService {
  readonly certPath = getRuntimeCertPath();
  readonly keyPath = getRuntimeCertKeyPath();
  readonly legacyMitmCaPath = getLegacyMitmCaPath();
  readonly runtimeLegacyMitmCaCertPath = getRuntimeLegacyMitmCaCertPath();
  private keyPem = "";
  private certPem = "";
  private caCert: ReturnType<typeof forge.pki.createCertificate> | null = null;
  private caKey: ReturnType<typeof forge.pki.privateKeyFromPem> | null = null;
  private hostCertCache = new Map<string, { certPem: string; keyPem: string }>();
  private certificateBundle: CertificateBundle | null = null;

  ensureCertificate(): CertificateBundle {
    if (this.certificateBundle && this.caCert && this.caKey && this.certPem && this.keyPem) {
      return this.certificateBundle;
    }
    ensureDir(getRuntimeCertDir());
    const legacy = this.readLegacyMitmCertificate();
    if (legacy) {
      this.certificateBundle = legacy;
      return legacy;
    }
    if (existsSync(this.certPath) && existsSync(this.keyPath)) {
      this.certPem = readFileSync(this.certPath, "utf-8");
      this.keyPem = readFileSync(this.keyPath, "utf-8");
      this.caCert = forge.pki.certificateFromPem(this.certPem);
      this.caKey = forge.pki.privateKeyFromPem(this.keyPem);
      this.certificateBundle = {
        certPem: this.certPem,
        keyPem: this.keyPem,
        certPath: this.certPath,
        trustCertPath: this.certPath,
        commonName: this.getCommonName(this.certPem)
      };
      return this.certificateBundle;
    }

    if (!forge.pki?.rsa?.generateKeyPair) {
      throw new Error("node-forge RSA 模块不可用，请重新安装依赖");
    }
    const keys = forge.pki.rsa.generateKeyPair(2048);
    const cert = forge.pki.createCertificate();
    cert.publicKey = keys.publicKey;
    cert.serialNumber = String(Date.now());
    cert.validity.notBefore = new Date();
    cert.validity.notAfter = new Date();
    cert.validity.notAfter.setFullYear(cert.validity.notBefore.getFullYear() + 5);
    const attrs = [{ name: "commonName", value: "SignSignIn Local Proxy CA" }];
    cert.setSubject(attrs);
    cert.setIssuer(attrs);
    cert.setExtensions([
      { name: "basicConstraints", cA: true },
      { name: "keyUsage", keyCertSign: true, digitalSignature: true, cRLSign: true },
      { name: "subjectKeyIdentifier" },
      { name: "authorityKeyIdentifier", keyIdentifier: true }
    ]);
    cert.sign(keys.privateKey, forge.md.sha256.create());

    this.certPem = forge.pki.certificateToPem(cert);
    this.keyPem = forge.pki.privateKeyToPem(keys.privateKey);
    this.caCert = cert;
    this.caKey = keys.privateKey;
    writeFileSync(this.certPath, this.certPem, "utf-8");
    writeFileSync(this.keyPath, this.keyPem, "utf-8");
    this.certificateBundle = {
      certPem: this.certPem,
      keyPem: this.keyPem,
      certPath: this.certPath,
      trustCertPath: this.certPath,
      commonName: "SignSignIn Local Proxy CA"
    };
    return this.certificateBundle;
  }

  private readLegacyMitmCertificate(): CertificateBundle | null {
    if (!existsSync(this.legacyMitmCaPath)) return null;
    const pem = readFileSync(this.legacyMitmCaPath, "utf-8");
    const certPem = pem.match(/-----BEGIN CERTIFICATE-----[\s\S]+?-----END CERTIFICATE-----/)?.[0];
    const keyPem = pem.match(/-----BEGIN (?:RSA )?PRIVATE KEY-----[\s\S]+?-----END (?:RSA )?PRIVATE KEY-----/)?.[0];
    if (!certPem || !keyPem) return null;
    this.certPem = certPem;
    this.keyPem = keyPem;
    this.caCert = forge.pki.certificateFromPem(certPem);
    this.caKey = forge.pki.privateKeyFromPem(keyPem);
    logger.info(`复用旧版 mitmproxy CA: ${this.legacyMitmCaPath}`);
    return {
      certPem,
      keyPem,
      certPath: this.legacyMitmCaPath,
      trustCertPath: this.ensureLegacyTrustCert(certPem),
      commonName: this.getCommonName(certPem)
    };
  }

  createHostCertificate(hostname: string): { certPem: string; keyPem: string } {
    const host = hostname.split(":")[0].trim().toLowerCase();
    const cached = this.hostCertCache.get(host);
    if (cached) return cached;
    this.ensureCertificate();
    if (!this.caCert || !this.caKey) throw new Error("本地 CA 证书未初始化");

    const keys = forge.pki.rsa.generateKeyPair(2048);
    const cert = forge.pki.createCertificate();
    cert.publicKey = keys.publicKey;
    // 序列号必须是正整数；十六进制字符串首位若是 8-F 会被解析为负数，加 "00" 兜底
    cert.serialNumber = `00${Date.now().toString(16)}${Math.floor(Math.random() * 0xffff).toString(16).padStart(4, "0")}`;
    cert.validity.notBefore = new Date();
    cert.validity.notBefore.setDate(cert.validity.notBefore.getDate() - 1);
    cert.validity.notAfter = new Date();
    cert.validity.notAfter.setFullYear(cert.validity.notBefore.getFullYear() + 2);
    cert.setSubject([
      { name: "commonName", value: host },
      { name: "organizationName", value: "mitmproxy" }
    ]);
    cert.setIssuer(this.caCert.subject.attributes);

    const isIp = /^\d{1,3}(\.\d{1,3}){3}$/.test(host);
    const altNames = isIp
      ? [{ type: 7, ip: host }]
      : [{ type: 2, value: host }];

    cert.setExtensions([
      { name: "basicConstraints", cA: false },
      { name: "keyUsage", critical: true, digitalSignature: true, keyEncipherment: true },
      { name: "extKeyUsage", serverAuth: true, clientAuth: true },
      { name: "subjectAltName", altNames },
      { name: "subjectKeyIdentifier" },
      {
        name: "authorityKeyIdentifier",
        keyIdentifier: this.caCert.generateSubjectKeyIdentifier().getBytes()
      }
    ]);
    cert.sign(this.caKey, forge.md.sha256.create());

    const pair = {
      certPem: `${forge.pki.certificateToPem(cert)}\n${this.certPem}`,
      keyPem: forge.pki.privateKeyToPem(keys.privateKey)
    };
    this.hostCertCache.set(host, pair);
    return pair;
  }

  async isTrusted(): Promise<boolean> {
    const cert = this.ensureCertificate();
    if (isMacos()) {
      return this.macosCertificateTrusted(cert);
    }
    if (isWindows()) {
      const result = await execAsync(`certutil -user -store root "${cert.commonName}"`).catch(() => null);
      return Boolean(result?.stdout && result.stdout.includes(cert.commonName));
    }
    return existsSync(this.certPath);
  }

  async ensureTrusted(): Promise<void> {
    const cert = this.ensureCertificate();
    if (await this.isTrusted()) {
      logger.info("本地 CA 证书已在系统中受信任");
      return;
    }
    if (isMacos()) {
      logger.info(`正在安装并信任本地 CA 证书到 System keychain（需要管理员密码）: ${cert.trustCertPath}`);
      // Chromium / BoringSSL（WeChatAppEx）在 macOS 上要求公网域名证书带 SCT，
      // 唯一豁免条件是签发 CA 装在 admin trust（/Library/Keychains/System.keychain）。
      // 仅放在 user login keychain 时客户端会以 alert 46 (certificate_unknown) 拒绝握手。
      const systemKeychain = "/Library/Keychains/System.keychain";
      const escapedPath = cert.trustCertPath.replace(/"/g, '\\"');
      const shellCmd = `/usr/bin/security add-trusted-cert -d -r trustRoot -k "${systemKeychain}" "${escapedPath}"`;
      const osaScript = `do shell script "${shellCmd.replace(/"/g, '\\"')}" with administrator privileges`;
      const installed = await execFileAsync("/usr/bin/osascript", ["-e", osaScript])
        .then(() => true)
        .catch((error) => {
          logger.warn(`自动信任证书失败：${error instanceof Error ? error.message : String(error)}`);
          return false;
        });
      if (!installed) {
        logger.warn(`请手动将 ${cert.trustCertPath} 拖入【钥匙串访问 → 系统】并设为「始终信任」`);
        await openCertManager().catch(() => false);
        throw new Error(
          `自动信任证书失败，请手动在【钥匙串访问 → 系统】导入并将 ${cert.commonName} 设为始终信任：${cert.trustCertPath}`
        );
      }
      if (!(await this.isTrusted())) {
        await openCertManager().catch(() => false);
        throw new Error(`本地 CA 证书安装后仍未通过信任校验，请在【钥匙串访问 → 系统】中将 ${cert.commonName} 设为始终信任`);
      }
      logger.info("本地 CA 证书已安装到 System keychain 并设为信任根证书");
      return;
    }
    if (isWindows()) {
      logger.info(`正在安装并信任本地 CA 证书: ${cert.trustCertPath}`);
      await execFileAsync("certutil", ["-user", "-addstore", "Root", cert.trustCertPath]);
      if (!(await this.isTrusted())) {
        throw new Error("本地 CA 证书安装后仍未通过信任校验，请在证书管理器中手动导入到受信任根证书");
      }
      logger.info("本地 CA 证书已安装并设为信任根证书");
      return;
    }
    throw new Error("当前系统暂不支持自动信任证书");
  }

  async openManager(): Promise<boolean> {
    return openCertManager();
  }

  private ensureLegacyTrustCert(certPem: string): string {
    const cert = forge.pki.certificateFromPem(certPem);
    const der = forge.asn1.toDer(forge.pki.certificateToAsn1(cert)).getBytes();
    writeFileSync(this.runtimeLegacyMitmCaCertPath, Buffer.from(der, "binary"));
    return this.runtimeLegacyMitmCaCertPath;
  }

  private getCommonName(certPem: string): string {
    const cert = forge.pki.certificateFromPem(certPem);
    const cn = cert.subject.getField("CN")?.value;
    return typeof cn === "string" && cn ? cn : "SignSignIn Local Proxy CA";
  }

  private async macosCertificateTrusted(cert: CertificateBundle): Promise<boolean> {
    // 必须验证 CA 是否进入 admin trust（System.keychain 域），否则 Chromium/BoringSSL
    // 仍会以 alert 46 拒绝公网域名（CT 强制要求私有 CA 走 admin trust 才豁免）。
    const inSystem = await execFileAsync("/usr/bin/security", [
      "find-certificate",
      "-c",
      cert.commonName,
      "/Library/Keychains/System.keychain"
    ])
      .then(() => true)
      .catch(() => false);
    if (!inSystem) return false;

    const result = await execFileAsync("/usr/bin/security", [
      "verify-cert",
      "-p",
      "ssl",
      "-c",
      cert.trustCertPath,
      "-L",
      "-q"
    ]).catch(() => null);
    return result !== null;
  }
}

export const certService = new CertService();
