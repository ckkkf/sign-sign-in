import { existsSync, statSync } from "node:fs";
import { basename, extname } from "node:path";
import type { JieLongFileInfo } from "@shared/types";

const IMAGE_EXTS: Record<string, string> = {
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".bmp": "image/bmp",
  ".gif": "image/gif",
  ".webp": "image/webp"
};

export function contentTypeFor(path: string): string {
  return IMAGE_EXTS[extname(path).toLowerCase()] || "image/jpeg";
}

function validateImagePath(path: string): string {
  const value = String(path || "").trim();
  if (!value || !existsSync(value) || !statSync(value).isFile()) throw new Error("图片文件不存在");
  if (!IMAGE_EXTS[extname(value).toLowerCase()]) throw new Error("仅支持 PNG/JPG/JPEG/BMP/GIF/WEBP 图片");
  return value;
}

export function buildLocalMediaFiles(imagePaths: string[]): JieLongFileInfo[] {
  return (imagePaths || []).map((rawPath) => {
    const path = validateImagePath(rawPath);
    return {
      Name: basename(path),
      FileName: basename(path),
      ContentType: contentTypeFor(path),
      Size: statSync(path).size,
      LocalPath: path
    };
  });
}
