import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "InTeam · AI 新员工入职助手",
  description: "企业新员工 AI 入职助手",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-full">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
