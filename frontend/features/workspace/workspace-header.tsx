"use client";

import { LogOut } from "lucide-react";
import Image from "next/image";

import type { UserInfo } from "@/lib/api/types";

type WorkspaceHeaderProps = {
  user: UserInfo;
  onLogout: () => void;
};

export function WorkspaceHeader({ user, onLogout }: WorkspaceHeaderProps) {
  return (
    <header className="workspace-header">
      <div className="workspace-brand">
        <Image className="workspace-logo" src="/brand/inteam-logo.svg" alt="InTeam" width={118} height={32} priority />
        <span className="company-badge">星澜科技</span>
      </div>
      <div className="workspace-user">
        <span className="onboard-day">AI 新员工入职助手</span>
        <span className="user-avatar">{user.name.slice(0, 1)}</span>
        <span className="user-name">{user.name}</span>
        <button className="icon-button" type="button" onClick={onLogout} aria-label="退出登录"><LogOut size={16} /></button>
      </div>
    </header>
  );
}
