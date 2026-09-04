import { WorkspaceApp } from "@/features/workspace/workspace-app";

// 生产 CSP 使用请求级 nonce；页面必须动态渲染，才能让脚本标签携带
// 与当前响应头一致的 nonce，不能复用构建时生成的静态 HTML。
export const dynamic = "force-dynamic";

export default function Home() {
  return <WorkspaceApp />;
}
