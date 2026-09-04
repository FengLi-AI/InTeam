"use client";

import { ListChecks, Map, MessageCircle } from "lucide-react";

export type MobileSection = "chat" | "map" | "plan";

type MobileNavProps = {
  active: MobileSection;
  onChange: (section: MobileSection) => void;
};

const ITEMS = [
  { id: "chat" as const, label: "问 Agent", icon: MessageCircle },
  { id: "map" as const, label: "上手地图", icon: Map },
  { id: "plan" as const, label: "我的计划", icon: ListChecks },
];

export function MobileNav({ active, onChange }: MobileNavProps) {
  return (
    <nav className="mobile-nav" aria-label="移动端主导航">
      {ITEMS.map(({ id, label, icon: Icon }) => (
        <button type="button" key={id} aria-current={active === id ? "page" : undefined} onClick={() => onChange(id)}>
          <Icon size={19} /><span>{label}</span>
        </button>
      ))}
    </nav>
  );
}
