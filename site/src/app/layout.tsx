import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MingOff · 明代内阁年表",
  description:
    "明代职官数据库——按年查看内阁在任者，每条记录可溯源史料来源。数据：张德信《明代职官年表》。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
