import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "你的AI外贸业务员",
  description: "对话即获客：告诉 AI 你想找什么客户，剩下的交给我。",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="font-system">{children}</body>
    </html>
  );
}
