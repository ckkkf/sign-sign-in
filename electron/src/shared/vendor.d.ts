declare module "sm-crypto" {
  export const sm2: {
    doEncrypt: (msg: string, publicKey: string, cipherMode?: number) => string;
  };
}
