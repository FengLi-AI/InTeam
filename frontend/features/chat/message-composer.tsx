"use client";

import { ArrowUp, LoaderCircle, MessageSquareText, Square } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { BorderGlow, TextType } from "@/features/effects/motion-primitives";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  busy: boolean;
  stopping: boolean;
  disabled?: boolean;
  stopDisabled?: boolean;
  lockWhileBusy?: boolean;
  label: string;
  sendLabel: string;
  stopLabel: string;
  examples: string[];
  id?: string;
  maxLength?: number;
  variant?: "chat" | "prepare";
};

export function MessageComposer({ value, onChange, onSubmit, onStop, busy, stopping, disabled = false, stopDisabled = false, lockWhileBusy = false, label, sendLabel, stopLabel, examples, id, maxLength, variant = "chat" }: Props) {
  const [focused, setFocused] = useState(false);
  const [height, setHeight] = useState(56);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    let frame = 0;
    let width = -1;
    function resize() {
      if (!textarea || textarea.clientWidth === 0) return;
      cancelAnimationFrame(frame);
      const current = textarea.getBoundingClientRect().height || 56;
      const transition = textarea.style.transition;
      textarea.style.transition = "none";
      textarea.style.height = "56px";
      const next = Math.max(56, Math.min(160, textarea.scrollHeight));
      textarea.style.height = `${current}px`;
      void textarea.offsetHeight;
      textarea.style.transition = transition;
      frame = requestAnimationFrame(() => {
        setHeight(next);
        textarea.style.height = `${next}px`;
      });
    }
    resize();
    // Re-measure on mode switches and column/viewport resizing, not only typing.
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => {
      if (width !== textarea.clientWidth) { width = textarea.clientWidth; resize(); }
    });
    observer?.observe(textarea);
    return () => { cancelAnimationFrame(frame); observer?.disconnect(); };
  }, [value]);

  const submitDisabled = disabled || !value.trim();
  return <BorderGlow className={`chat-composer-glow composer-${variant} ${height > 62 ? "is-multiline" : "is-single-line"}`}>
    <div className="chat-composer">
      <p className="composer-shortcuts"><MessageSquareText size={12} /> Enter 发送 · Shift + Enter 换行</p>
      {!value && !focused && <div className="composer-type-hint" aria-hidden="true"><TextType texts={examples} /></div>}
      <textarea ref={textareaRef} id={id} value={value} onChange={(event) => onChange(event.target.value)} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            if (!busy && !submitDisabled) onSubmit();
          }
        }} rows={1} style={{ height: `${height}px` }} placeholder="" aria-label={label} maxLength={maxLength} disabled={busy && lockWhileBusy} />
      <button className={busy ? "is-stop" : ""} type="button" onClick={busy ? onStop : onSubmit} disabled={busy ? stopping || stopDisabled : submitDisabled} aria-label={busy ? stopLabel : sendLabel}>
        {busy ? (stopping ? <LoaderCircle className="spin" size={18} /> : <Square size={15} />) : <ArrowUp size={18} />}
      </button>
    </div>
  </BorderGlow>;
}
