// [Input] Markdown text from chat message parts (assistant, user, plan popover).
// [Output] GFM Markdown rendered through the shared chain, with ```mermaid blocks routed to MermaidBlock.
// [Pos] chat-markdown component node in frontend/src/components/chat
// [Sync] 2026-07-20: created per docs/design/claude-agent/chat-markdown-mermaid.md — consolidates the
//                    three local ReactMarkdown+remarkGfm call sites; `pre` override unwraps Mermaid
//                    blocks so no block-level element is nested inside <pre>.
import { Children, isValidElement, memo, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import MermaidBlock from './MermaidBlock';

const REMARK_PLUGINS = [remarkGfm];

function extractText(node: ReactNode): string {
  if (typeof node === 'string') {
    return node;
  }
  if (Array.isArray(node)) {
    return node.map(extractText).join('');
  }
  return '';
}

const COMPONENTS: Components = {
  code({ className, children }) {
    if (className === 'language-mermaid') {
      return <MermaidBlock chart={extractText(children)} />;
    }
    return <code className={className}>{children}</code>;
  },
  pre({ children }) {
    // Mermaid code blocks render a block-level MermaidBlock; unwrapping the <pre>
    // keeps the DOM valid (<pre> only accepts phrasing content). The child here is
    // the (not yet invoked) custom `code` component element, so detect Mermaid via
    // its props.className rather than its rendered type.
    const child = Children.toArray(children)[0];
    if (isValidElement<{ className?: string }>(child) && child.props.className === 'language-mermaid') {
      return <>{children}</>;
    }
    return <pre>{children}</pre>;
  },
};

interface ChatMarkdownProps {
  text: string;
}

export default memo(function ChatMarkdown({ text }: ChatMarkdownProps) {
  return <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={COMPONENTS}>{text}</ReactMarkdown>;
});
