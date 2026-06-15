import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AMZ 选品工作台",
  description: "运营 × AI 交互式亚马逊选品工作台",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
