"use client";

import { useEffect, useRef, useState } from "react";

export function useScrollAffordance() {
  const ref = useRef<HTMLDivElement>(null);
  const timerRef = useRef<number | null>(null);
  const [edges, setEdges] = useState({ top: false, bottom: false, moving: false });

  function update(moving = false) {
    const element = ref.current;
    if (!element) return;
    setEdges({
      top: element.scrollTop > 8,
      bottom: element.scrollTop + element.clientHeight < element.scrollHeight - 8,
      moving: moving || edges.moving,
    });
    if (moving) {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(() => setEdges((current) => ({ ...current, moving: false })), 650);
    }
  }

  useEffect(() => {
    update(false);
    const element = ref.current;
    if (!element) return;
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => update(false));
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    return () => {
      observer.disconnect();
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
    // The first measurement intentionally runs once after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const className = [edges.top && "can-fade-top", edges.bottom && "can-fade-bottom", edges.moving && "is-scrolling"].filter(Boolean).join(" ");
  return { ref, className, onScroll: () => update(true) };
}
