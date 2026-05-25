import { copyFileSync, existsSync, readFileSync, readdirSync, renameSync, statSync, unlinkSync } from "node:fs";
import { basename, extname, join, resolve, sep } from "node:path";
import { dialog, shell } from "electron";
import type { ImageItem } from "@shared/types";
import { ensureDir, getRuntimeImageDir } from "./paths";

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"]);

function isAllowedImage(path: string): boolean {
  return IMAGE_EXTS.has(extname(path).toLowerCase());
}

function imageMime(path: string): string {
  const ext = extname(path).toLowerCase();
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".bmp") return "image/bmp";
  if (ext === ".gif") return "image/gif";
  if (ext === ".webp") return "image/webp";
  return "image/png";
}

function toImageItem(path: string): ImageItem {
  const stat = statSync(path);
  return {
    name: basename(path),
    path,
    previewUrl: `data:${imageMime(path)};base64,${readFileSync(path).toString("base64")}`,
    size: stat.size,
    updatedAt: stat.mtimeMs
  };
}

export class ImageStore {
  list(): ImageItem[] {
    const dir = getRuntimeImageDir();
    ensureDir(dir);
    return readdirSync(dir)
      .map((name) => join(dir, name))
      .filter((path) => existsSync(path) && statSync(path).isFile() && isAllowedImage(path))
      .sort()
      .map(toImageItem);
  }

  private imageDir(): string {
    const dir = getRuntimeImageDir();
    ensureDir(dir);
    return dir;
  }

  private resolveImagePath(path: string): string {
    const dir = resolve(this.imageDir());
    const target = resolve(path);
    if (target === dir || !target.startsWith(`${dir}${sep}`)) throw new Error("只能管理图片目录中的文件");
    if (!existsSync(target) || !statSync(target).isFile()) throw new Error("图片不存在");
    if (!isAllowedImage(target)) throw new Error("仅支持 PNG/JPG/JPEG/BMP/GIF/WEBP 图片");
    return target;
  }

  private async chooseImage(title: string): Promise<string> {
    const result = await dialog.showOpenDialog({
      title,
      properties: ["openFile"],
      filters: [{ name: "Images", extensions: ["png", "jpg", "jpeg", "bmp", "gif", "webp"] }]
    });
    if (result.canceled || !result.filePaths[0]) {
      throw new Error("未选择图片");
    }
    return result.filePaths[0];
  }

  private validateName(name: string): string {
    const trimmed = name.trim();
    if (!trimmed) throw new Error("图片名称不能为空");
    if (trimmed.includes("/") || trimmed.includes("\\") || trimmed.includes(sep)) throw new Error("图片名称不能包含路径分隔符");
    if (!isAllowedImage(trimmed)) throw new Error("仅支持 PNG/JPG/JPEG/BMP/GIF/WEBP 图片");
    return trimmed;
  }

  async import(): Promise<ImageItem> {
    const source = await this.chooseImage("选择拍照签到图片");
    if (!isAllowedImage(source)) throw new Error("仅支持 PNG/JPG/JPEG/BMP/GIF/WEBP 图片");
    const dir = this.imageDir();

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
    return toImageItem(target);
  }

  rename(path: string, name: string): ImageItem {
    const source = this.resolveImagePath(path);
    const safeName = this.validateName(name);
    const target = join(this.imageDir(), safeName);
    if (resolve(source) === resolve(target)) return toImageItem(source);
    if (existsSync(target)) throw new Error("同名图片已存在");
    renameSync(source, target);
    return toImageItem(target);
  }

  async replace(path: string): Promise<ImageItem> {
    const oldPath = this.resolveImagePath(path);
    const source = await this.chooseImage("选择替换图片");
    if (!isAllowedImage(source)) throw new Error("仅支持 PNG/JPG/JPEG/BMP/GIF/WEBP 图片");

    const oldExt = extname(oldPath);
    const sourceExt = extname(source);
    const oldName = basename(oldPath);
    const stem = oldName.slice(0, oldName.length - oldExt.length);
    const target = sourceExt.toLowerCase() === oldExt.toLowerCase() ? oldPath : join(this.imageDir(), `${stem}${sourceExt}`);
    if (target !== oldPath && existsSync(target)) throw new Error("替换后的文件名已存在");
    copyFileSync(source, target);
    if (target !== oldPath) unlinkSync(oldPath);
    return toImageItem(target);
  }

  delete(path: string): boolean {
    const target = this.resolveImagePath(path);
    unlinkSync(target);
    return true;
  }

  async openDir(): Promise<boolean> {
    await shell.openPath(this.imageDir());
    return true;
  }
}

export const imageStore = new ImageStore();
