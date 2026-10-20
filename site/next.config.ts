import type { NextConfig } from "next";
import path from "path";

// GitHub Pages 项目站部署在 /<repo>/ 子路径下；需要在构建时指定 basePath。
// 本地构建不设该环境变量，保持根路径。
const basePath = process.env.NEXT_BASE_PATH || undefined;

const nextConfig: NextConfig = {
  // D22：静态导出，零运维部署（GitHub Pages / Vercel 均可）
  output: "export",
  ...(basePath ? { basePath, assetPrefix: basePath } : {}),
  // 工作区根定位到 site/，避免被外层 lockfile 干扰
  outputFileTracingRoot: path.resolve(__dirname),
};

export default nextConfig;