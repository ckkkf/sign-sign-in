import type { AxiosResponse } from "axios";
import FormData from "form-data";
import { createReadStream } from "node:fs";
import { basename, extname } from "node:path";
import { AMAP_WEB_KEY, TENCENT_MAP_KEY, XYB_REFERER, XYB_VERSION } from "@shared/constants";
import type { SignConfig, SignOption } from "@shared/types";
import { logger } from "../services/logger";
import { sessionStore } from "../services/sessionStore";
import { getDeviceCode, getHeaderToken } from "../services/xybToken";
import { http } from "./httpClient";
import type { GeoResponse, LoginArgs, UploadPolicy, XybResponse } from "./types/xybTypes";

/** 从校友邦接口响应中提取可读消息。 */
function responseMessage(data: unknown): string {
  if (data && typeof data === "object") {
    const body = data as { msg?: unknown; message?: unknown };
    const msg = body.msg ?? body.message;

    if (msg !== undefined && msg !== null && String(msg).trim()) {
      return String(msg);
    }
  }

  return JSON.stringify(data);
}

/** 调用高德逆地理编码接口，把经纬度解析为地址。 */
export async function regeo(config: SignConfig["input"]): Promise<GeoResponse> {
  if (String(config.mapProvider || "amap").toLowerCase() === "tencent") {
    return regeoTencent(config);
  }

  logger.info("正在调用高德地图解析经纬度...");

  // 按当前签到坐标请求高德逆地理编码。
  const response = await http.get("https://restapi.amap.com/v3/geocode/regeo", {
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

  if (!data?.regeocode) {
    throw new Error(`位置解析失败: ${JSON.stringify(data)}`);
  }

  const geo = data.regeocode as GeoResponse;

  // 高德偶发不返回格式化地址时，用坐标兜底展示。
  if (!geo.formatted_address) {
    geo.formatted_address = `${config.location.longitude},${config.location.latitude}`;
  }

  logger.info(`解析位置: ${geo.formatted_address}`);
  return geo;
}

async function regeoTencent(config: SignConfig["input"]): Promise<GeoResponse> {
  logger.info("正在调用腾讯地图解析经纬度...");

  const response = await http.get("https://apis.map.qq.com/ws/geocoder/v1/", {
    headers: {
      xweb_xhr: "1",
      Referer: XYB_REFERER,
      "User-Agent": config.userAgent
    },
    params: {
      location: `${config.location.latitude},${config.location.longitude}`,
      key: TENCENT_MAP_KEY,
      get_poi: "1"
    }
  });

  const data = response.data;
  if (response.status !== 200 || data?.status !== 0 || !data?.result) {
    throw new Error(`位置解析失败: ${JSON.stringify(data)}`);
  }

  const result = data.result;
  const component = result.address_component || {};
  const adInfo = result.ad_info || {};
  const formatted = result.formatted_addresses || {};
  const geo: GeoResponse = {
    formatted_address:
      formatted.recommend ||
      formatted.rough ||
      result.address ||
      formatted.standard_address ||
      `${config.location.longitude},${config.location.latitude}`,
    addressComponent: {
      province: component.province || "",
      city: component.city || component.province || "",
      district: component.district || "",
      street: component.street || "",
      streetNumber: component.street_number || "",
      adcode: adInfo.adcode || ""
    }
  };

  logger.info(`解析位置: ${geo.formatted_address}`);
  return geo;
}

/** 用小程序 code 换取校友邦 openId 信息。 */
export async function getOpenId(config: SignConfig["input"], code: string): Promise<Record<string, string>> {
  logger.info("正在获取 openId...");

  // getOpenId 接口只需要 wx.login 捕获到的 code。
  const response = await http.post(
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
    throw new Error(`code已失效，请重启小程序。接口响应：${responseMessage(body)}`);
  }

  if (!body.data) {
    throw new Error(`获取OpenID失败: ${responseMessage(body)}`);
  }

  return body.data;
}

/** 使用 openId 信息完成校友邦微信登录。 */
export async function wxLogin(config: SignConfig["input"], openIdData: Record<string, string>): Promise<Record<string, string>> {
  logger.info("正在进行微信登录...");

  const data = {
    openId: openIdData.openId,
    unionId: openIdData.unionId
  };
  const token = getHeaderToken(data);

  // login!wx.action 返回 encryptValue 和 JSESSIONID。
  const response = await http.post(
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

  if (!body.data) {
    throw new Error(`登录失败: ${responseMessage(body)}`);
  }

  return body.data;
}

/** 获取校友邦会话参数，优先使用本地缓存。 */
export async function login(config: SignConfig["input"], useCache = true): Promise<LoginArgs> {
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

  if (!code) {
    throw new Error("Code为空，请重新获取");
  }

  // 新 code 流程：先换 openId，再登录拿 session。
  const openIdData = await getOpenId(config, code);
  const loginData = await wxLogin(config, openIdData);
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

/** 获取当前账号可用的实习计划列表。 */
export async function getPlan(config: SignConfig["input"], args: LoginArgs): Promise<any[]> {
  logger.info("正在获取实习计划...");

  const data: Record<string, string> = {};
  const token = getHeaderToken(data);

  // 计划接口不带 devicecode，保持 Python 版请求行为。
  const response = await formPost("https://xcx.xybsyw.com/student/clock/GetPlan.action", data, {
    config,
    args,
    token,
    includeDeviceCode: false
  });
  const body = requireValidResponse<any[]>(response, "获取计划失败");

  if (!Array.isArray(body)) {
    throw new Error(`获取计划失败: ${responseMessage(response.data)}`);
  }

  return body;
}

/** 执行普通签到或签退。 */
export async function simpleSignInOrOut(
  args: LoginArgs,
  config: SignConfig["input"],
  geo: GeoResponse,
  traineeId: string,
  opt: SignOption
): Promise<string> {
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

  // 普通签到接口不携带图片地址。
  const response = await formPost("https://xcx.xybsyw.com/student/clock/Post.action", data, {
    config,
    args,
    token,
    includeDeviceCode: true
  });
  const body = response.data as XybResponse;
  assertSession(body);

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

/** 获取拍照签到图片上传凭证。 */
export async function commonPostPolicy(args: LoginArgs, config: SignConfig["input"]): Promise<UploadPolicy> {
  logger.info("正在获取上传凭证...");

  const data = {
    customerType: "STUDENT",
    uploadType: "UPLOAD_STUDENT_CLOCK_IMGAGES",
    publicRead: "true"
  };
  const token = getHeaderToken(data);

  // 上传凭证接口返回 OSS host、policy、签名和 callback。
  const response = await formPost("https://xcx.xybsyw.com/uploadfile/commonPostPolicy.action", data, {
    config,
    args,
    token,
    includeDeviceCode: true
  });
  return requireValidResponse<UploadPolicy>(response, "获取上传凭证失败");
}

/** 上传拍照签到图片到阿里云 OSS。 */
export async function aliyunOSS(
  filePath: string,
  policy: UploadPolicy,
  timestamp: number,
  userAgent: string
): Promise<{ key: string }> {
  logger.info("正在上传至阿里云OSS...");

  const ext = extname(filePath) || ".jpg";
  const key = `${policy.dir}/${timestamp}${ext}`;
  const form = new FormData();

  // OSS 表单字段必须使用上传凭证返回的签名参数。
  form.append("key", key);
  form.append("policy", policy.policy);
  form.append("OSSAccessKeyId", policy.accessid);
  form.append("signature", policy.signature);
  form.append("success_action_status", "200");
  form.append("customerType", policy.customParams["x:customer_type_key"]);
  form.append("uploadType", policy.customParams["x:upload_type_key"]);
  form.append("callback", policy.callback);
  form.append("file", createReadStream(filePath), basename(filePath));

  // 图片上传成功后，OSS callback 会返回校友邦可用的 key。
  const response = await http.post(policy.host, form, {
    headers: {
      ...form.getHeaders(),
      Referer: XYB_REFERER,
      "User-Agent": userAgent
    },
    maxBodyLength: Infinity
  });

  if (response.status !== 200) {
    throw new Error(`aliyun_OSS请求异常: ${response.status} ${JSON.stringify(response.data)}`);
  }

  return response.data.vo;
}

/** 执行拍照签到或签退。 */
export async function photoSignInOrOut(
  args: LoginArgs,
  config: SignConfig["input"],
  geo: GeoResponse,
  traineeId: string,
  opt: SignOption
): Promise<string> {
  if (!opt.imagePath) {
    throw new Error("请先为拍照签到选择图片");
  }

  // 先上传图片，再用返回的 key 提交拍照签到。
  const policy = await commonPostPolicy(args, config);
  const timestamp = Date.now();
  const ossData = await aliyunOSS(opt.imagePath, policy, timestamp, config.userAgent);
  await postNew(args, config, traineeId, geo, ossData.key, opt);
  return `${opt.action}成功！`;
}

/** 提交拍照签到记录。 */
export async function postNew(
  args: LoginArgs,
  config: SignConfig["input"],
  traineeId: string,
  geo: GeoResponse,
  imgUrl: string,
  opt: SignOption
): Promise<void> {
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

  // PostNew 接口用于携带图片地址的签到。
  const response = await formPost("https://xcx.xybsyw.com/student/clock/PostNew.action", data, {
    config,
    args,
    token,
    includeDeviceCode: true
  });
  requireValidResponse(response, "拍照签到失败");
}

/** 发送校友邦表单 POST 请求。 */
async function formPost(
  url: string,
  data: Record<string, string>,
  options: {
    config: SignConfig["input"];
    args: LoginArgs;
    token: ReturnType<typeof getHeaderToken>;
    includeDeviceCode: boolean;
  }
): Promise<AxiosResponse> {
  // 每个表单请求都需要 m/n/s/t 签名和 JSESSIONID。
  return http.post(url, new URLSearchParams(data), {
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

/** 校验校友邦登录态是否仍有效。 */
function assertSession(body: XybResponse): void {
  if (body.code === "205" || body.code === 205 || String(body.msg || "").includes("未登录")) {
    sessionStore.clear();
    throw new Error("JSESSIONID已失效，已清除缓存，请重新获取code");
  }
}

/** 校验校友邦业务响应并返回 data。 */
function requireValidResponse<T = unknown>(response: AxiosResponse, context: string): T {
  const body = response.data as XybResponse<T>;
  assertSession(body);

  if (response.status !== 200 || !(body.code === "200" || body.code === 200) || body.data === undefined) {
    throw new Error(`${context}: ${responseMessage(body)}`);
  }

  return body.data;
}
