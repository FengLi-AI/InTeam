"use client";

import { useMutation } from "@tanstack/react-query";
import { BookOpen, ChevronDown, ExternalLink, FileText, Folder, Library, LoaderCircle, Settings } from "lucide-react";
import { useState } from "react";

import { safeExternalUrl } from "@/app/lib/security";
import { getDocIntro } from "@/lib/api/workspace";
import type { DocItem } from "@/lib/api/types";

type LibraryPanelProps = {
  docs: DocItem[];
  loading: boolean;
  error: boolean;
};

export function LibraryPanel({ docs, loading, error }: LibraryPanelProps) {
  const [view, setView] = useState<"list" | "folder">("list");
  const [openToken, setOpenToken] = useState<string | null>(null);
  const [intros, setIntros] = useState<Record<string, string>>({});
  const introMutation = useMutation({
    mutationFn: getDocIntro,
    onSuccess: (intro, token) => setIntros((current) => ({ ...current, [token]: intro })),
  });

  function toggleDoc(doc: DocItem) {
    const next = openToken === doc.doc_token ? null : doc.doc_token;
    setOpenToken(next);
    if (next && !intros[next]) introMutation.mutate(next);
  }

  return (
    <aside className="panel library-panel" aria-label="公司资料库">
      <div className="panel-heading library-heading">
        <div className="panel-title-wrap">
          <span className="panel-title-icon"><Library size={17} /></span>
          <div>
            <p className="eyebrow">KNOWLEDGE</p>
            <h2>公司资料库</h2>
          </div>
        </div>
        <div className="segmented-control" aria-label="资料显示方式">
          <button type="button" aria-pressed={view === "list"} onClick={() => setView("list")}><FileText size={14} /></button>
          <button type="button" aria-pressed={view === "folder"} onClick={() => setView("folder")}><Folder size={14} /></button>
        </div>
      </div>

      <div className="library-content scroll-area">
        {loading && <p className="quiet-state"><LoaderCircle className="spin" size={16} /> 正在同步资料</p>}
        {!loading && error && <p className="quiet-state error-text">资料暂时无法加载，请稍后刷新</p>}
        {!loading && !error && docs.length === 0 && <p className="quiet-state">暂无同步文档</p>}

        {docs.map((doc) => {
          const open = openToken === doc.doc_token;
          const url = safeExternalUrl(doc.url);
          return (
            <article className={`doc-item ${open ? "is-open" : ""}`} key={doc.doc_token}>
              <button className="doc-trigger" type="button" aria-expanded={open} onClick={() => toggleDoc(doc)}>
                <span className="doc-icon">{view === "folder" ? <Folder size={16} /> : <FileText size={16} />}</span>
                <span className="doc-name">{doc.title}</span>
                <ChevronDown className="doc-chevron" size={15} />
              </button>
              <div className="doc-disclosure" aria-hidden={!open}>
                <div className="doc-summary">
                  <p className="summary-label"><BookOpen size={13} /> AI 导读</p>
                  {introMutation.isPending && introMutation.variables === doc.doc_token ? (
                    <p className="summary-copy"><LoaderCircle className="spin" size={14} /> 正在阅读文档…</p>
                  ) : (
                    <p className="summary-copy">{intros[doc.doc_token] ?? "展开后生成这份文档的入职导读。"}</p>
                  )}
                  {url && (
                    <a className="text-action" href={url} target="_blank" rel="noopener noreferrer">
                      查看原文 <ExternalLink size={13} />
                    </a>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <button className="library-settings" type="button" disabled title="设置将在后续版本开放">
        <Settings size={16} /><span>设置</span><span className="coming-soon">稍后开放</span>
      </button>
    </aside>
  );
}
