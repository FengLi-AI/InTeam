"""邀请码生成命令行入口。

用法（在 backend 目录下）：
    .venv/bin/python cli_invite.py generate --count 10 --note "内测批次1"
    .venv/bin/python cli_invite.py revoke IT-XXXX-XXXX
"""
from __future__ import annotations

import argparse

from app.services.invite import create_invites, revoke_invite


def main() -> int:
    parser = argparse.ArgumentParser(description="InTeam 邀请码管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="批量生成邀请码")
    gen.add_argument("--count", type=int, default=10, help="生成数量")
    gen.add_argument("--note", default="", help="备注")

    rev = sub.add_parser("revoke", help="作废邀请码")
    rev.add_argument("code", help="邀请码")

    args = parser.parse_args()

    if args.cmd == "generate":
        codes = create_invites(args.count, args.note)
        print(f"已生成 {len(codes)} 个邀请码：")
        for code in codes:
            print(f"  {code}")
        return 0

    if args.cmd == "revoke":
        ok = revoke_invite(args.code.strip().upper())
        print("已作废" if ok else "未找到该码或已作废")
        return 0 if ok else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
