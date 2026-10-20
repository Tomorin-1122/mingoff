import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // D22：静态导出，零运维部署（Vercel / GitHub Pages 均可）
  output: "export",
  // 工作区根定位到 site/，避免被外层 lockfile 干扰
  outputFileTracingRoot: path.resolve(__dirname),
};

export default nextConfig;
