import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "明代职官数据库 · MingOff",
  description:
    "明代内阁年表——按年月查看在任者，每条记录可溯源史料来源。数据：张德信《明代职官年表》册1。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-Hant">
      <body className="site-body">{children}</body>
    </html>
  );
}
