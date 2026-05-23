export const PROJECT_NAME = "Sign sign in";
export const PROJECT_VERSION = "v1.3.1";
export const PROJECT_GITHUB = "https://github.com/ckkkf/sign-sign-in";
export const QQ_GROUP = "859098272";

export const XYB_VERSION = "1.6.40";
export const XYB_KEY = "ZsE4rGnjI9PkHqAz2WseDc4RF8Uh7YgVMb5Ke48NemJ4saA6XcQ821fFT061pC";
export const XYB_APP_ID = "wx9f1c2e0bbc10673c";
export const XYB_REFERER_ID = "560";
export const XYB_REFERER = `https://servicewechat.com/${XYB_APP_ID}/${XYB_REFERER_ID}/page-frame.html`;
export const AMAP_WEB_KEY = "c222383ff12d31b556c3ad6145bb95f4";
export const MITM_HOST = "127.0.0.1";
export const MITM_PORT = 13140;

export const XYB_SM2_PUBLIC_KEY =
  "04a3c35de075a2e86f28d52a41989a08e740a82fb96d43d9af8a5509e0a4e837ecb384c44fe1ee95f601ef36f3c892214d45c9b3f75b57556466876ad6052f0f1f";
export const XYB_SM2_MODE = 1;

export const XYB_EXCLUDED_KEYS = [
  "content",
  "deviceName",
  "keyWord",
  "blogBody",
  "blogTitle",
  "getType",
  "responsibilities",
  "street",
  "text",
  "reason",
  "searchvalue",
  "key",
  "answers",
  "leaveReason",
  "personRemark",
  "selfAppraisal",
  "imgUrl",
  "wxname",
  "deviceId",
  "avatarTempPath",
  "file",
  "model",
  "brand",
  "system",
  "platform",
  "code",
  "openId",
  "unionid",
  "clockDeviceToken",
  "clockDevice",
  "address",
  "name",
  "enterpriseEmail",
  "practiceTarget",
  "guardianName",
  "guardianPhone",
  "practiceDays",
  "linkman",
  "enterpriseName",
  "companyIntroduction",
  "accommodationStreet",
  "accommodationLongitude",
  "accommodationLatitude",
  "internshipDestination",
  "specialStatement",
  "enterpriseStreet",
  "insuranceName",
  "insuranceFinancing",
  "policyNumber",
  "overtimeRemark",
  "riskStatement"
];

export const XYB_N_HEADER = XYB_EXCLUDED_KEYS.join(",");

export const UA_TEMPLATE =
  "Mozilla/5.0 (Linux; {system}; {model} Build/BP2A.250605.015; wv) " +
  "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 " +
  "Mobile Safari/537.36 XWEB/1420229 MMWEBSDK/20240404 MMWEBID/9843 " +
  "MicroMessenger/8.0.49.2600(0x28003133) WeChat/arm64 Weixin NetType/5G " +
  "Language/zh_CN ABI/arm64 MiniProgramEnv/{platform}";
