"use client";

import { useCallback, useSyncExternalStore } from "react";

type PanelSide = "library" | "schedule";

const DEFAULTS = { library: 300, schedule: 420 };
const LIMITS = {
  library: { min: 260, max: 360 },
  schedule: { min: 340, max: 440 },
};

function readWidth(side: PanelSide) {
  if (typeof window === "undefined") return DEFAULTS[side];
  const parsed = Number(window.localStorage.getItem(`inteam:v2:${side}-width`));
  return Number.isFinite(parsed) ? Math.min(LIMITS[side].max, Math.max(LIMITS[side].min, parsed)) : DEFAULTS[side];
}

export function usePanelWidths() {
  const subscribe = useCallback((callback: () => void) => {
    window.addEventListener("storage", callback);
    window.addEventListener("inteam:panel-width", callback);
    return () => {
      window.removeEventListener("storage", callback);
      window.removeEventListener("inteam:panel-width", callback);
    };
  }, []);
  const libraryWidth = useSyncExternalStore(subscribe, () => readWidth("library"), () => DEFAULTS.library);
  const scheduleWidth = useSyncExternalStore(subscribe, () => readWidth("schedule"), () => DEFAULTS.schedule);

  function writeWidth(side: PanelSide, width: number) {
    window.localStorage.setItem(`inteam:v2:${side}-width`, String(width));
    window.dispatchEvent(new Event("inteam:panel-width"));
  }

  function beginResize(side: PanelSide, event: React.PointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId);
    const startX = event.clientX;
    const startWidth = side === "library" ? libraryWidth : scheduleWidth;

    function move(moveEvent: PointerEvent) {
      const delta = moveEvent.clientX - startX;
      const raw = side === "library" ? startWidth + delta : startWidth - delta;
      const next = Math.round(Math.min(LIMITS[side].max, Math.max(LIMITS[side].min, raw)) / 8) * 8;
      writeWidth(side, next);
    }

    function finish() {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", finish);
    }

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", finish, { once: true });
  }

  return { libraryWidth, scheduleWidth, beginResize };
}
