import { copyFileSync, existsSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { basename, extname, join, resolve, sep } from "node:path";
import { dialog } from "electron";
import type { ImageItem } from "@shared/types";
import { ensureDir, getRuntimeImageDir } from "./paths";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]);

function isAllowedImage(path: string): boolean {
  return IMAGE_EXTS.has(extname(path).toLowerCase());
}

export class ImageStore {
  list(): ImageItem[] {
    const dir = getRuntimeImageDir();
    ensureDir(dir);
    return readdirSync(dir)
      .map((name) => join(dir, name))
      .filter((path) => existsSync(path) && statSync(path).isFile() && isAllowedImage(path))
      .sort()
      .map((path) => ({ name: basename(path), path }));
  }

  async import(): Promise<ImageItem> {
    const result = await dialog.showOpenDialog({
      title: "选择拍照签到图片",
      properties: ["openFile"],
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "bmp", "gif", "webp"] }]
    });
    if (result.canceled || !result.filePaths[0]) {
      throw new Error("未选择图片");
    }
    const source = result.filePaths[0];
    if (!isAllowedImage(source)) throw new Error("仅支持 PNG/JPG/JPEG/BMP/GIF/WEBP 图片");
    const dir = getRuntimeImageDir();
    ensureDir(dir);

    const parsed = basename(source);
    const ext = extname(parsed);
    const stem = parsed.slice(0, parsed.length - ext.length);
    let target = join(dir, parsed);
    let index = 1;
    while (existsSync(target)) {
      target = join(dir, `${stem}_${index}${ext}`);
      index += 1;
    }
    copyFileSync(source, target);
    return { name: basename(target), path: target };
  }

  delete(path: string): boolean {
    const dir = resolve(getRuntimeImageDir());
    const target = resolve(path);
    if (target !== dir && !target.startsWith(`${dir}${sep}`)) throw new Error("只能删除图片目录中的文件");
    if (existsSync(target)) unlinkSync(target);
    return true;
  }
}

export const imageStore = new ImageStore();
