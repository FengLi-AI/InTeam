"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

export default function AuthCallback() {
  const router = useRouter();
  const done = useRef(false);

  useEffect(() => {
    if (done.current) return;
    done.current = true;

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");

    if (!code) {
      router.replace("/");
      return;
    }

    fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, state: state || "" }),
    })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then(() => undefined)
      .catch(() => {
        /* 登录失败回到首页，让用户重试 */
      })
      .finally(() => router.replace("/"));
  }, [router]);

  return (
    <div className="flex h-dvh items-center justify-center">
      <p className="text-sm text-gray-400">正在登录…</p>
    </div>
  );
}
