/** RuoYi 风格通用接口响应。 */
export interface AjaxResult<T> {
  code?: number | string;
  msg?: string;
  data?: T;
  token?: string;
  tokenName?: string;
}
