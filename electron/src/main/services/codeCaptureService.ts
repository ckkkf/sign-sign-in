import { createServer, request as httpRequest, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { connect as connectTcp, type Socket } from "node:net";
import { connect as connectTls, createSecureContext, createServer as createTlsServer, type TLSSocket } from "node:tls";
import { EventEmitter } from "node:events";
import { URL } from "node:url";
import { MITM_HOST, MITM_PORT, XYB_APP_ID } from "@shared/constants";
import type { CaptureState } from "@shared/types";
import { logger } from "./logger";
import { certService } from "./certService";
import { setSystemProxy, resetSystemProxy, killWeChatAppEx, wakeApplet } from "./systemService";

const CONNECT_OK = "HTTP/1.1 200 Connection Established\r\n\r\n";
const MAX_CAPTURE_BUFFER = 256 * 1024;

export class CodeCaptureService extends EventEmitter {
  private server: Server | null = null;
  private sockets = new Set<Socket>();
  private originProxy = "";
  private lastCode = "";
  private message = "";
  private autoStopping = false;

  getState(): CaptureState {
    return {
      running: Boolean(this.server?.listening),
      host: MITM_HOST,
      port: MITM_PORT,
      lastCode: this.lastCode,
      message: this.message
    };
  }

  async start(): Promise<CaptureState> {
    if (this.server) return this.getState();
    await certService.ensureTrusted();
    await this.startNodeProxy();
    const target = `${MITM_HOST}:${MITM_PORT}`;
    try {
      this.originProxy = await setSystemProxy(target);
      this.message = `代理已启动并设置为 ${target}`;
      logger.info(this.message);
    } catch (error) {
      this.message = `代理已启动，但系统代理设置失败：${error instanceof Error ? error.message : String(error)}`;
      logger.warn(this.message);
    }

    // 关闭微信小程序渲染进程 + 唤起校友邦小程序，强制其重发 wx.login → getOpenId.action
    // 这一步如果跳过，已经打开的小程序会用本地缓存的 openId 而不发请求，导致 mitm 抓不到 code
    try {
      const attempted = await killWeChatAppEx();
      if (attempted > 0) {
        logger.info("🧹 已尝试关闭小程序渲染进程");
      }
      await wakeApplet(XYB_APP_ID);
      logger.info(`🌈 已发送唤醒指令到微信 (appid=${XYB_APP_ID})`);
      logger.info("⏳ 请等待校友邦小程序加载，以获取 code...");
    } catch (error) {
      logger.warn(`唤醒微信小程序失败：${error instanceof Error ? error.message : String(error)}`);
    }

    return this.getState();
  }

  async stop(): Promise<CaptureState> {
    const target = `${MITM_HOST}:${MITM_PORT}`;
    if (this.server) {
      const server = this.server;
      this.server = null;
      for (const socket of this.sockets) {
        socket.destroy();
      }
      this.sockets.clear();
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
    await resetSystemProxy(this.originProxy, target).catch((error) => {
      logger.warn(`恢复系统代理失败：${error instanceof Error ? error.message : String(error)}`);
    });
    this.originProxy = "";
    this.message = "代理已停止";
    logger.info(this.message);
    return this.getState();
  }

  setManualCode(code: string): CaptureState {
    this.lastCode = code.trim();
    this.message = this.lastCode ? "已手动写入 code" : "已清空 code";
    logger.info(this.message);
    return this.getState();
  }

  consumeCode(): string {
    return this.lastCode;
  }

  private async startNodeProxy(): Promise<void> {
    const server = createServer((request, response) => this.handleHttpRequest(request, response));
    server.on("connect", (request, socket, head) => this.handleConnect(request, socket as Socket, head));
    server.on("clientError", (error, socket) => {
      logger.debug(`Node 代理客户端错误: ${error.message}`);
      socket.destroy();
    });
    this.server = server;
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(MITM_PORT, MITM_HOST, () => {
        server.off("error", reject);
        resolve();
      });
    });
    logger.info("Node 代理已启用 HTTPS MITM 捕获模式");
  }

  private handleHttpRequest(clientRequest: IncomingMessage, clientResponse: ServerResponse): void {
    const host = String(clientRequest.headers.host || "");
    if (!host) {
      clientResponse.writeHead(400);
      clientResponse.end("Missing Host");
      return;
    }
    let targetUrl: URL;
    try {
      targetUrl = new URL(clientRequest.url || "/", `http://${host}`);
    } catch {
      clientResponse.writeHead(400);
      clientResponse.end("Bad Request");
      return;
    }
    this.inspectHttpText(host, `${clientRequest.method || "GET"} ${targetUrl.pathname}${targetUrl.search} HTTP/1.1\r\n`);
    const upstream = httpRequest(
      {
        hostname: targetUrl.hostname,
        port: targetUrl.port || 80,
        method: clientRequest.method,
        path: `${targetUrl.pathname}${targetUrl.search}`,
        headers: this.cleanProxyHeaders(clientRequest.headers)
      },
      (upstreamResponse) => {
        clientResponse.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
        upstreamResponse.pipe(clientResponse);
      }
    );
    upstream.on("error", (error) => {
      logger.warn(`HTTP 代理转发失败: ${host} ${error.message}`);
      if (!clientResponse.headersSent) clientResponse.writeHead(502);
      clientResponse.end();
    });
    clientRequest.on("data", (chunk: Buffer) => this.inspectHttpText(host, chunk.toString("utf-8")));
    clientRequest.pipe(upstream);
  }

  private handleConnect(request: IncomingMessage, clientSocket: Socket, head: Buffer): void {
    const { host, port } = this.parseConnectTarget(request.url || "");
    if (!host || !port) {
      clientSocket.end("HTTP/1.1 400 Bad Request\r\n\r\n");
      return;
    }
    if (!this.shouldMitmHost(host)) {
      this.openRawTunnel(host, port, clientSocket, head);
      return;
    }
    logger.info(`HTTPS MITM 命中: ${host}:${port}`);
    this.openMitmTunnel(host, port, clientSocket, head);
  }

  private openRawTunnel(host: string, port: number, clientSocket: Socket, head: Buffer): void {
    const upstream = connectTcp(port, host, () => {
      clientSocket.write(CONNECT_OK);
      if (head.length) upstream.write(head);
      upstream.pipe(clientSocket);
      clientSocket.pipe(upstream);
    });
    this.trackSocket(clientSocket);
    this.trackSocket(upstream);
    upstream.on("error", (error) => {
      logger.debug(`HTTPS 隧道连接失败: ${host}:${port} ${error.message}`);
      clientSocket.destroy();
    });
  }

  private openMitmTunnel(host: string, port: number, clientSocket: Socket, head: Buffer): void {
    const cert = certService.createHostCertificate(host);
    // 把 cert/key 直接放在 server 顶层选项 + secureContext 双保险。
    // Node 18+/Electron 的 boringssl 在 TLS1.3 路径下，仅 secureContext 不够会报 NO_CERTIFICATE_SET。
    const tlsServer = createTlsServer({
      cert: cert.certPem,
      key: cert.keyPem,
      // SNI 回调里也按 servername 现挂证书，给客户端 Mismatch 时兜底
      SNICallback: (servername, cb) => {
        try {
          const sniCert = certService.createHostCertificate(servername || host);
          cb(
            null,
            createSecureContext({
              cert: sniCert.certPem,
              key: sniCert.keyPem
            })
          );
        } catch (error) {
          cb(error instanceof Error ? error : new Error(String(error)));
        }
      }
    });
    tlsServer.once("secureConnection", (clientTls) => {
      logger.debug(`HTTPS MITM 本地 TLS 已建立: ${host}:${port}`);
      this.openUpstreamTls(host, port, clientTls);
    });
    tlsServer.on("tlsClientError", (error) => {
      logger.warn(`HTTPS MITM TLS 握手失败: ${host}:${port} ${error.message}`);
      clientSocket.destroy();
    });
    clientSocket.write(CONNECT_OK, () => {
      if (head.length) clientSocket.unshift(head);
      tlsServer.emit("connection", clientSocket);
    });
  }

  private openUpstreamTls(host: string, port: number, clientTls: TLSSocket): void {
    const upstream = connectTls({
      host,
      port,
      servername: host,
      rejectUnauthorized: false
    });
    this.trackSocket(clientTls);
    this.trackSocket(upstream);

    // 关键：upstream 还没 secureConnect 之前 client 已经在发 ClientHello → HTTP 请求字节，
    // 必须缓存起来，secureConnect 后一次性 flush，再开 pipe。
    // 直接 pipe 会丢掉这之前的字节，并且我们 inspect 的是 *转发后* 的字节流。
    let upstreamReady = false;
    const pendingFromClient: Buffer[] = [];
    let captureBuffer = "";

    const inspectChunk = (chunk: Buffer) => {
      captureBuffer = `${captureBuffer}${chunk.toString("utf-8")}`;
      if (captureBuffer.length > MAX_CAPTURE_BUFFER) {
        captureBuffer = captureBuffer.slice(-MAX_CAPTURE_BUFFER);
      }
      this.inspectHttpText(host, captureBuffer);
    };

    clientTls.on("data", (chunk: Buffer) => {
      inspectChunk(chunk);
      if (upstreamReady) {
        upstream.write(chunk);
      } else {
        pendingFromClient.push(chunk);
      }
    });

    upstream.on("error", (error) => {
      logger.warn(`HTTPS MITM 上游连接失败: ${host}:${port} ${error.message}`);
      clientTls.destroy();
    });
    clientTls.on("error", (error) => {
      logger.debug(`HTTPS MITM 客户端连接关闭: ${host}:${port} ${error.message}`);
      upstream.destroy();
    });
    clientTls.on("end", () => upstream.end());
    upstream.on("end", () => clientTls.end());

    upstream.on("secureConnect", () => {
      upstreamReady = true;
      for (const chunk of pendingFromClient) upstream.write(chunk);
      pendingFromClient.length = 0;
      // 反向：上游响应直接转给客户端
      upstream.pipe(clientTls);
    });
  }

  private inspectHttpText(host: string, text: string): void {
    if (!this.shouldCaptureText(host, text)) return;
    const code = this.extractCode(text);
    if (!code || code === this.lastCode) return;
    this.lastCode = code;
    this.message = "已捕获小程序 code";
    logger.info(`已捕获小程序 code: ${code}`);
    // 抓到 code 后立刻关闭小程序渲染进程，下次启动 capture 时能保证拿到全新的 wx.login code
    void killWeChatAppEx().then((n) => {
      if (n > 0) logger.info("🧹 已关闭小程序渲染进程，避免缓存导致下次抓不到 code");
    });
    this.emit("code", code);
    if (this.server && !this.autoStopping) {
      this.autoStopping = true;
      void this.stop()
        .catch((error) => logger.warn(`自动停止代理失败：${error instanceof Error ? error.message : String(error)}`))
        .finally(() => {
          this.autoStopping = false;
        });
    }
  }

  private shouldCaptureText(host: string, text: string): boolean {
    if (!this.shouldMitmHost(host)) return false;
    return /getOpenId\.action|login!wx\.action|[?&\s\r\n]code=|["']code["']\s*:/.test(text);
  }

  private extractCode(text: string): string {
    const jsonMatch = text.match(/["']code["']\s*:\s*["']([^"']+)["']/);
    if (jsonMatch?.[1]) return decodeURIComponent(jsonMatch[1]).trim();

    const requestLine = text.match(/^[A-Z]+\s+(\S+)\s+HTTP\/1\.[01]/m);
    const urlCode = requestLine?.[1] ? this.extractCodeFromParams(requestLine[1].split("?")[1] || "") : "";
    if (urlCode) return urlCode;

    const body = text.split("\r\n\r\n").pop() || text;
    return this.extractCodeFromParams(body);
  }

  private extractCodeFromParams(paramsText: string): string {
    try {
      const params = new URLSearchParams(paramsText);
      const code = params.get("code");
      if (code) return code.trim();
    } catch {
      // URLSearchParams can parse most form bodies; regex below handles malformed fragments.
    }
    const match = paramsText.match(/(?:^|[?&\s])code=([^&\s\r\n]+)/);
    return match?.[1] ? decodeURIComponent(match[1]).trim() : "";
  }

  private shouldMitmHost(host: string): boolean {
    const cleanHost = host.split(":")[0].toLowerCase();
    return cleanHost === "xybsyw.com" || cleanHost.endsWith(".xybsyw.com");
  }

  private parseConnectTarget(target: string): { host: string; port: number } {
    const index = target.lastIndexOf(":");
    if (index <= 0) return { host: "", port: 0 };
    const host = target.slice(0, index).replace(/^\[|\]$/g, "");
    const port = Number(target.slice(index + 1));
    return { host, port: Number.isFinite(port) ? port : 0 };
  }

  private cleanProxyHeaders(headers: IncomingMessage["headers"]): IncomingMessage["headers"] {
    const cleaned = { ...headers };
    delete cleaned["proxy-connection"];
    delete cleaned["proxy-authorization"];
    return cleaned;
  }

  private trackSocket<T extends Socket>(socket: T): T {
    this.sockets.add(socket);
    socket.once("close", () => this.sockets.delete(socket));
    socket.once("error", () => this.sockets.delete(socket));
    return socket;
  }

  private handleMitmOutput(chunk: Buffer): void {
    const text = chunk.toString("utf-8").trim();
    if (!text) return;
    for (const line of text.split(/\r?\n/)) {
      logger.debug(`Node MITM: ${line}`);
    }
  }
}

export const codeCaptureService = new CodeCaptureService();
