/** 校友邦接口通用响应。 */
export interface XybResponse<T = unknown> {
  code: string | number;
  msg?: string;
  data?: T;
}

/** 校友邦登录态参数。 */
export interface LoginArgs {
  openId: string;
  unionId: string;
  encryptValue: string;
  sessionId: string;
  traineeId?: string;
}

/** 高德逆地理编码响应。 */
export interface GeoResponse {
  formatted_address: string;
  addressComponent: {
    adcode: string;
    [key: string]: unknown;
  };
}

/** 校友邦图片上传凭证。 */
export interface UploadPolicy {
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
