"use client";

import dynamic from "next/dynamic";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";

const AeroShards = dynamic(() => import("./AeroShards"), { ssr: false });
const Aurora = dynamic(() => import("./Aurora"), { ssr: false });

export function FoldText({ children, className = "" }: { children: string; className?: string }) {
  const glyphs = useMemo(() => Array.from(children), [children]);
  return (
    <span className={`fold-text ${className}`} aria-label={children}>
      {glyphs.map((glyph, index) => (
        <span aria-hidden="true" key={`${glyph}-${index}`} style={{ "--fold-index": index } as CSSProperties}>
          {glyph === " " ? "\u00a0" : glyph}
        </span>
      ))}
    </span>
  );
}

export function ShinyText({
  children,
  className = "",
  disabled = false,
  duration = 4,
}: {
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  duration?: number;
}) {
  return (
    <span
      className={`shiny-text ${disabled ? "is-disabled" : ""} ${className}`}
      style={{ "--shiny-duration": `${duration}s` } as CSSProperties}
    >
      {children}
    </span>
  );
}

export function TextType({ texts, className = "" }: { texts: string[]; className?: string }) {
  const [textIndex, setTextIndex] = useState(0);
  const [length, setLength] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const current = texts[textIndex] ?? "";
    const complete = length === current.length;
    const empty = length === 0;
    const delay = complete && !deleting ? 1500 : deleting ? 24 : 45;
    const timer = window.setTimeout(() => {
      if (complete && !deleting) setDeleting(true);
      else if (empty && deleting) {
        setDeleting(false);
        setTextIndex((value) => (value + 1) % texts.length);
      } else setLength((value) => value + (deleting ? -1 : 1));
    }, delay);
    return () => window.clearTimeout(timer);
  }, [deleting, length, textIndex, texts]);

  const current = texts[textIndex] ?? "";
  return <span className={`text-type ${className}`}>{current.slice(0, length)}<span aria-hidden="true" className="text-type-caret" /></span>;
}

export function BorderGlow({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`border-glow ${className}`}>{children}</div>;
}

export function AeroShardsLayer() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px) and (prefers-reduced-motion: no-preference)");
    const sync = () => setEnabled(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  if (!enabled) return null;

  return <AeroShards
    className="aero-shards-layer"
    backgroundColor="#f7f9ff"
    shardColor="#6479ef"
    accentColor="#a9b7ff"
    placement="full"
    flow="vortex"
    material="pearl"
    detail="fine"
    scale={1.1}
    spread={1.1}
    depth={1.18}
    speed={0.06}
    spin={0.42}
    interaction="attract"
    density={0.88}
    shardSize={0.66}
    stretch={0.82}
    turbulence={0.66}
    glow={0.45}
    bloom={0.18}
    grain={0.015}
    chromaticAberration={0.002}
    transitionDuration={1.1}
    interactionRadius={1.8}
    interactionStrength={0.72}
    rippleIntensity={0.65}
    holdToGather
  />;
}

export function AuroraLayer() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px) and (prefers-reduced-motion: no-preference)");
    const sync = () => setEnabled(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  if (!enabled) return null;

  return (
    <div className="aurora-workspace-layer" aria-hidden="true">
      <Aurora
        colorStops={["#e5ddf1", "#c9d7ee", "#d2cef9"]}
        amplitude={1}
        blend={0.75}
        lightMode
      />
    </div>
  );
}
