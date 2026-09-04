import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function safeMarkdownUrl(value: string): string {
  if (value.startsWith("#")) return value;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.toString() : "";
  } catch {
    return "";
  }
}

export function MarkdownMessage({ children }: { children: string }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        urlTransform={safeMarkdownUrl}
        components={{
          a: ({ href, children: linkChildren }) => href
            ? <a href={href} target="_blank" rel="noopener noreferrer">{linkChildren}</a>
            : <span>{linkChildren}</span>,
          img: ({ alt }) => alt ? <span className="markdown-image-alt">[图片：{alt}]</span> : null,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
