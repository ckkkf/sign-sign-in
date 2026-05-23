import axios, { type AxiosInstance, type AxiosResponse } from "axios";
import FormData from "form-data";
import { createReadStream } from "node:fs";
import { basename, extname } from "node:path";
import { AMAP_WEB_KEY, XYB_REFERER, XYB_VERSION } from "@shared/constants";
import type { SignConfig, SignOption } from "@shared/types";
import { getDeviceCode, getHeaderToken } from "./xybToken";
import { sessionStore } from "./sessionStore";
import { logger } from "./logger";

type XybResponse<T = unknown> = {
  code: string | number;
  msg?: string;
  data?: T;
};

export interface LoginArgs {
  openId: string;
  unionId: string;
  encryptValue: string;
  sessionId: string;
  traineeId?: string;
}

interface GeoResponse {
  formatted_address: string;
  addressComponent: {
    adcode: string;
    [key: string]: unknown;
  };
}

interface UploadPolicy {
  host: string;
  dir: string;
  policy: string;
  accessid: string;
  signature: string;
  callback: string;
  customParams: {
    "x:customer_type_key": string;
    "x:upload_type_key": string;
  };
}

export class XybClient {
  private readonly http: AxiosInstance;

  constructor() {
    this.http = axios.create({
      timeout: 15000,
      maxRedirects: 0,
      validateStatus: () => true
    });
  }

  async regeo(config: SignConfig["input"]): Promise<GeoResponse> {
    logger.info("正在调用高德地图解析经纬度...");
    const response = await this.http.get("https://restapi.amap.com/v3/geocode/regeo", {
      headers: {
        xweb_xhr: "1",
        "Content-Type": "application/json",
        Referer: XYB_REFERER,
        "User-Agent": config.userAgent
      },
      params: {
        s: "rsx",
        platform: "WXJS",
        logversion: "2.0",
        extensions: "all",
        sdkversion: "1.2.0",
        key: AMAP_WEB_KEY,
        appname: AMAP_WEB_KEY,
        location: `${config.location.longitude},${config.location.latitude}`
      }
    });
    const data = response.data;
    if (!data?.regeocode) throw new Error(`位置解析失败: ${JSON.stringify(data)}`);
    const geo = data.regeocode as GeoResponse;
    if (!geo.formatted_address) {
      geo.formatted_address = `${config.location.longitude},${config.location.latitude}`;
    }
    logger.info(`解析位置: ${geo.formatted_address}`);
    return geo;
  }

  async getOpenId(config: SignConfig["input"], code: string): Promise<Record<string, string>> {
    logger.info("正在获取 openId...");
    const response = await this.http.post(
      "https://xcx.xybsyw.com/common/getOpenId.action",
      new URLSearchParams({ code }),
      {
        headers: {
          v: XYB_VERSION,
          xweb_xhr: "1",
          "content-type": "application/x-www-form-urlencoded",
          referer: XYB_REFERER,
          "User-Agent": config.userAgent,
          devicecode: getDeviceCode("", config.device)
        }
      }
    );
    const body = response.data as XybResponse<Record<string, string>>;
    if (body.code === "202" || body.code === 202) {
      throw new Error(`code已失效，请重启小程序。接口响应：${JSON.stringify(body)}`);
    }
    if (!body.data) throw new Error(`获取OpenID失败: ${JSON.stringify(body)}`);
    return body.data;
  }

  async wxLogin(config: SignConfig["input"], openIdData: Record<string, string>): Promise<Record<string, string>> {
    logger.info("正在进行微信登录...");
    const data = {
      openId: openIdData.openId,
      unionId: openIdData.unionId
    };
    const token = getHeaderToken(data);
    const response = await this.http.post(
      "https://xcx.xybsyw.com/login/login!wx.action",
      new URLSearchParams(data),
      {
        headers: {
          wechat: "1",
          v: XYB_VERSION,
          xweb_xhr: "1",
          "content-type": "application/x-www-form-urlencoded",
          referer: XYB_REFERER,
          n: token.n,
          devicecode: getDeviceCode(openIdData.openId, config.device),
          encryptvalue: openIdData.encryptValue,
          m: token.m,
          s: token.s,
          t: token.t,
          "user-agent": config.userAgent,
          Cookie: `JSESSIONID=${openIdData.sessionId}`
        }
      }
    );
    const body = response.data as XybResponse<Record<string, string>>;
    if (!body.data) throw new Error(`登录失败: ${JSON.stringify(body)}`);
    return body.data;
  }

  async login(config: SignConfig["input"], useCache = true): Promise<LoginArgs> {
    if (useCache) {
      const cached = sessionStore.read();
      if (cached) {
        logger.info("使用缓存的 JSESSIONID");
        return {
          openId: cached.openId,
          unionId: cached.unionId,
          encryptValue: cached.encryptValue,
          sessionId: cached.sessionId,
          traineeId: cached.traineeId
        };
      }
    }
    const code = config.code;
    if (!code) throw new Error("Code为空，请重新获取");
    const openIdData = await this.getOpenId(config, code);
    const loginData = await this.wxLogin(config, openIdData);
    const result: LoginArgs = {
      openId: openIdData.openId,
      unionId: openIdData.unionId,
      encryptValue: loginData.encryptValue,
      sessionId: loginData.sessionId
    };
    sessionStore.save(result);
    logger.info("登录成功，已缓存 JSESSIONID");
    return result;
  }

  async getPlan(config: SignConfig["input"], args: LoginArgs): Promise<any[]> {
    logger.info("正在获取实习计划...");
    const data: Record<string, string> = {};
    const token = getHeaderToken(data);
    const response = await this.formPost("https://xcx.xybsyw.com/student/clock/GetPlan.action", data, {
      config,
      args,
      token,
      includeDeviceCode: false
    });
    const body = this.requireValidResponse<any[]>(response, "获取计划失败");
    if (!Array.isArray(body)) throw new Error(`获取计划失败: ${JSON.stringify(response.data)}`);
    return body;
  }

  async simpleSignInOrOut(args: LoginArgs, config: SignConfig["input"], geo: GeoResponse, traineeId: string, opt: SignOption): Promise<string> {
    logger.info(`正在调用接口进行: ${opt.action}...`);
    const device = config.device;
    const data = {
      punchInStatus: "0",
      clockStatus: String(opt.code),
      traineeId: String(traineeId),
      adcode: geo.addressComponent.adcode,
      model: device.model,
      brand: device.brand,
      platform: device.platform,
      system: device.system,
      openId: args.openId,
      unionId: args.unionId,
      lng: config.location.longitude,
      lat: config.location.latitude,
      address: geo.formatted_address,
      deviceName: device.model
    };
    const token = getHeaderToken(data);
    const response = await this.formPost("https://xcx.xybsyw.com/student/clock/Post.action", data, {
      config,
      args,
      token,
      includeDeviceCode: true
    });
    const body = response.data as XybResponse;
    this.assertSession(body);
    if (body.code === "200" || body.code === 200) {
      const msg = body.msg === "已经签到" ? `已经${opt.action}过了。` : `${opt.action}成功！`;
      logger.info(msg);
      return msg;
    }
    if (body.code === "403" || body.code === 403) {
      logger.warn(String(body.msg || "接口拒绝"));
      return String(body.msg || "接口拒绝");
    }
    if (body.code === "202" || body.code === 202) {
      throw new Error(`配置错误，请检查device和userAgent参数 (Code 202): ${body.msg}`);
    }
    throw new Error(`操作失败: ${body.msg || JSON.stringify(body)}`);
  }

  async commonPostPolicy(args: LoginArgs, config: SignConfig["input"]): Promise<UploadPolicy> {
    logger.info("正在获取上传凭证...");
    const data = {
      customerType: "STUDENT",
      uploadType: "UPLOAD_STUDENT_CLOCK_IMGAGES",
      publicRead: "true"
    };
    const token = getHeaderToken(data);
    const response = await this.formPost("https://xcx.xybsyw.com/uploadfile/commonPostPolicy.action", data, {
      config,
      args,
      token,
      includeDeviceCode: true
    });
    return this.requireValidResponse<UploadPolicy>(response, "获取上传凭证失败");
  }

  async aliyunOSS(filePath: string, policy: UploadPolicy, timestamp: number, userAgent: string): Promise<{ key: string }> {
    logger.info("正在上传至阿里云OSS...");
    const ext = extname(filePath) || ".jpg";
    const key = `${policy.dir}/${timestamp}${ext}`;
    const form = new FormData();
    form.append("key", key);
    form.append("policy", policy.policy);
    form.append("OSSAccessKeyId", policy.accessid);
    form.append("signature", policy.signature);
    form.append("success_action_status", "200");
    form.append("customerType", policy.customParams["x:customer_type_key"]);
    form.append("uploadType", policy.customParams["x:upload_type_key"]);
    form.append("callback", policy.callback);
    form.append("file", createReadStream(filePath), basename(filePath));
    const response = await this.http.post(policy.host, form, {
      headers: {
        ...form.getHeaders(),
        Referer: XYB_REFERER,
        "User-Agent": userAgent
      },
      maxBodyLength: Infinity
    });
    if (response.status !== 200) throw new Error(`aliyun_OSS请求异常: ${response.status} ${JSON.stringify(response.data)}`);
    return response.data.vo;
  }

  async photoSignInOrOut(args: LoginArgs, config: SignConfig["input"], geo: GeoResponse, traineeId: string, opt: SignOption): Promise<string> {
    if (!opt.imagePath) throw new Error("请先为拍照签到选择图片");
    const policy = await this.commonPostPolicy(args, config);
    const timestamp = Date.now();
    const ossData = await this.aliyunOSS(opt.imagePath, policy, timestamp, config.userAgent);
    await this.postNew(args, config, traineeId, geo, ossData.key, opt);
    return `${opt.action}成功！`;
  }

  async postNew(args: LoginArgs, config: SignConfig["input"], traineeId: string, geo: GeoResponse, imgUrl: string, opt: SignOption): Promise<void> {
    const data = {
      traineeId: String(traineeId),
      adcode: geo.addressComponent.adcode,
      lat: config.location.latitude,
      lng: config.location.longitude,
      address: geo.formatted_address,
      deviceName: config.device.model,
      punchInStatus: "0",
      clockStatus: String(opt.code),
      imgUrl,
      reason: "",
      addressId: "null"
    };
    const token = getHeaderToken(data);
    const response = await this.formPost("https://xcx.xybsyw.com/student/clock/PostNew.action", data, {
      config,
      args,
      token,
      includeDeviceCode: true
    });
    this.requireValidResponse(response, "拍照签到失败");
  }

  private async formPost(
    url: string,
    data: Record<string, string>,
    options: {
      config: SignConfig["input"];
      args: LoginArgs;
      token: ReturnType<typeof getHeaderToken>;
      includeDeviceCode: boolean;
    }
  ): Promise<AxiosResponse> {
    return this.http.post(url, new URLSearchParams(data), {
      headers: {
        "content-type": "application/x-www-form-urlencoded",
        encryptvalue: options.args.encryptValue,
        m: options.token.m,
        n: options.token.n,
        referer: XYB_REFERER,
        s: options.token.s,
        t: options.token.t,
        "user-agent": options.config.userAgent,
        v: XYB_VERSION,
        wechat: "1",
        xweb_xhr: "1",
        ...(options.includeDeviceCode ? { devicecode: getDeviceCode(options.args.openId, options.config.device) } : {}),
        Cookie: `JSESSIONID=${options.args.sessionId}`
      }
    });
  }

  private assertSession(body: XybResponse): void {
    if (body.code === "205" || body.code === 205 || String(body.msg || "").includes("未登录")) {
      sessionStore.clear();
      throw new Error("JSESSIONID已失效，已清除缓存，请重新获取code");
    }
  }

  private requireValidResponse<T = unknown>(response: AxiosResponse, context: string): T {
    const body = response.data as XybResponse<T>;
    this.assertSession(body);
    if (response.status !== 200 || !(body.code === "200" || body.code === 200) || body.data === undefined) {
      throw new Error(`${context}: ${body.msg || JSON.stringify(body)}`);
    }
    return body.data;
  }
}

export const xybClient = new XybClient();
