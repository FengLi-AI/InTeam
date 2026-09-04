"use client";

import { ArrowRight, KeyRound, LoaderCircle } from "lucide-react";
import Image from "next/image";
import { useState } from "react";

import { ShinyText } from "@/features/effects/motion-primitives";

type InviteLoginProps = {
  busy: boolean;
  error: string;
  onLogin: (inviteCode: string, nickname: string) => void;
};

export function InviteLogin({ busy, error, onLogin }: InviteLoginProps) {
  const [inviteCode, setInviteCode] = useState("");
  const [nickname, setNickname] = useState("");

  function submit() {
    const code = inviteCode.trim();
    if (!code || busy) return;
    onLogin(code, nickname.trim());
  }

  return (
    <main className="login-page">
      <div className="login-glow login-glow-one" />
      <div className="login-glow login-glow-two" />
      <section className="login-card">
        <div className="login-brand-icon" aria-hidden="true">
          <Image src="/brand/inteam-logo.svg" width={924} height={251} alt="" priority />
        </div>
        <h1 className="login-wordmark"><Image src="/brand/inteam-logo.svg" width={924} height={251} alt="InTeam" priority /></h1>
        <p className="eyebrow">WELCOME ABOARD</p>
        <p className="login-intro">用企业知识回答问题，把入职目标一步步变成可完成的行动。</p>

        <div className="login-fields">
          <label>
            <span>邀请码</span>
            <div className="field-shell"><KeyRound size={16} /><input autoFocus value={inviteCode} onChange={(event) => setInviteCode(event.target.value.toUpperCase())} onKeyDown={(event) => event.key === "Enter" && submit()} placeholder="输入你的邀请码" autoComplete="one-time-code" /></div>
          </label>
          <label>
            <span>昵称 <small>可选</small></span>
            <div className="field-shell"><input value={nickname} onChange={(event) => setNickname(event.target.value)} onKeyDown={(event) => event.key === "Enter" && submit()} placeholder="希望我们怎么称呼你" autoComplete="nickname" /></div>
          </label>
        </div>

        {error && <p className="login-error" role="alert">{error}</p>}
        <button className="login-submit" type="button" onClick={submit} disabled={!inviteCode.trim() || busy}>
          {busy ? <><LoaderCircle className="spin" size={17} />正在进入</> : <><ShinyText duration={3.4} disabled={!inviteCode.trim()}>进入 InTeam</ShinyText><ArrowRight size={17} /></>}
        </button>
        <p className="login-note">邀请码只用于验证访问权限，不会显示给其他成员。</p>
      </section>
    </main>
  );
}
