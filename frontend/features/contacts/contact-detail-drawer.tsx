"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Clipboard, MessageCircle, Plus, Sparkles, Tag, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Contact } from "@/lib/api/types";
import { addContactLabel, getContactDraft, getContactIntro } from "@/lib/api/workspace";

type DetailView = "intro" | "draft" | "labels" | null;

type ContactDetailDrawerProps = {
  contact: Contact;
  onClose: () => void;
  onLabelAdded?: (contactId: number, label: string) => void;
};

export function ContactDetailDrawer({ contact, onClose, onLabelAdded }: ContactDetailDrawerProps) {
  const [detailView, setDetailView] = useState<DetailView>(null);
  const [intro, setIntro] = useState("");
  const [draft, setDraft] = useState("");
  const [label, setLabel] = useState("");
  const [labels, setLabels] = useState(contact.labels);
  const [copied, setCopied] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;

      const focusable = Array.from(drawerRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ));
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    closeButtonRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      returnFocus?.focus();
    };
  }, [onClose]);

  const introMutation = useMutation({
    mutationFn: getContactIntro,
    onSuccess: setIntro,
  });
  const draftMutation = useMutation({
    mutationFn: getContactDraft,
    onSuccess: setDraft,
  });
  const labelMutation = useMutation({
    mutationFn: ({ id, value }: { id: number; value: string }) => addContactLabel(id, value),
    onSuccess: (_, variables) => {
      setLabels((current) => current.includes(variables.value) ? current : [...current, variables.value]);
      onLabelAdded?.(variables.id, variables.value);
      setLabel("");
    },
  });

  function showIntro() {
    setDetailView("intro");
    if (!intro && !introMutation.isPending) introMutation.mutate(contact.id);
  }

  function showDraft() {
    setDetailView("draft");
    draftMutation.mutate(contact.id);
  }

  async function copyDraft() {
    await navigator.clipboard?.writeText(draft);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="contact-drawer-root">
      <button className="contact-drawer-backdrop" type="button" aria-label="点击遮罩关闭同事详情" onClick={onClose} />
      <aside ref={drawerRef} className="contact-drawer" role="dialog" aria-modal="true" aria-labelledby={`contact-title-${contact.id}`}>
        <header className="contact-drawer-header">
          <span className="contact-drawer-avatar" aria-hidden="true">{contact.avatar_emoji || contact.name.slice(0, 1)}</span>
          <div>
            <p className="contact-kicker">{contact.department} · {contact.position}</p>
            <h2 id={`contact-title-${contact.id}`}>{contact.name}</h2>
          </div>
          <button ref={closeButtonRef} className="contact-close" type="button" onClick={onClose} aria-label="关闭同事详情"><X size={16} /></button>
        </header>

        <div className="contact-drawer-body">
          <p className="contact-duty">{contact.duty}</p>
          {contact.when_to_ask && (
            <div className="contact-when">
              <span>适合在这些情况找 TA</span>
              <p>{contact.when_to_ask}</p>
            </div>
          )}

          <div className="contact-actions" role="group" aria-label="同事操作">
            <button type="button" aria-pressed={detailView === "intro"} onClick={showIntro}><Sparkles size={15} />了解 TA</button>
            <button type="button" aria-pressed={detailView === "draft"} onClick={showDraft}><MessageCircle size={15} />沟通草稿</button>
            <button type="button" aria-pressed={detailView === "labels"} onClick={() => setDetailView("labels")}><Tag size={15} />备注</button>
          </div>

          {detailView === "intro" && (
            <div className="contact-result" aria-live="polite">
              <p>{introMutation.isPending ? "正在整理协作建议…" : introMutation.isError ? "生成失败，请重试" : intro}</p>
            </div>
          )}
          {detailView === "draft" && (
            <div className="contact-result" aria-live="polite">
              <p>{draftMutation.isPending ? "正在生成沟通草稿…" : draftMutation.isError ? "生成失败，请重试" : draft}</p>
              {draft && !draftMutation.isPending && (
                <button className="text-action" type="button" onClick={copyDraft}>{copied ? <Check size={13} /> : <Clipboard size={13} />}{copied ? "已复制" : "复制草稿"}</button>
              )}
            </div>
          )}
          {detailView === "labels" && (
            <div className="contact-result">
              {labels.length > 0 && <div className="contact-labels">{labels.map((item) => <span key={item}>{item}</span>)}</div>}
              <div className="label-create">
                <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="如：报销问题找他" aria-label="同事备注" />
                <button type="button" disabled={!label.trim() || labelMutation.isPending} onClick={() => labelMutation.mutate({ id: contact.id, value: label.trim() })}><Plus size={15} />保存</button>
              </div>
              {labelMutation.isError && <p className="contact-inline-error">保存失败，请重试</p>}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
