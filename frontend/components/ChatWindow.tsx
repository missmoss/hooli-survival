'use client';

import { useEffect, useRef } from 'react';

export type ChatMessage = {
  id: string;
  role: 'assistant' | 'user' | 'divider';
  content: string;
  generatedBy?: {
    provider?: string;
    model?: string;
  } | null;
};

type Props = {
  messages: ChatMessage[];
  assistantTyping?: boolean;
  showGeneratedBy?: boolean;
};

function generatedByLabel(generatedBy: ChatMessage['generatedBy']): string {
  if (!generatedBy) {
    return '';
  }
  const provider = (generatedBy.provider || '').trim();
  const model = (generatedBy.model || '').trim();
  if (provider && model) {
    return `${provider} · ${model}`;
  }
  return provider || model;
}

function dividerLabel(content: string): string {
  const cleaned = content.replace(/^[\s\-─—]+|[\s\-─—]+$/g, '').trim();
  return cleaned || content;
}

export default function ChatWindow({ messages, assistantTyping = false, showGeneratedBy = false }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const messageRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const previousMessageCountRef = useRef(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      previousMessageCountRef.current = messages.length;
      return;
    }

    const isInitialPaint = previousMessageCountRef.current === 0;
    const hasNewMessages = messages.length > previousMessageCountRef.current;
    previousMessageCountRef.current = messages.length;

    if (isInitialPaint) {
      container.scrollTop = 0;
      return;
    }

    if (assistantTyping || hasNewMessages) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }
  }, [assistantTyping, messages]);

  return (
    <div ref={containerRef} className="min-h-[16rem] flex-1 overflow-y-auto p-0">
      <div className="space-y-4">
        {messages.map((msg) => {
          if (msg.role === 'divider') {
            return (
              <div key={msg.id} className="px-1 py-1 text-[12px] mono text-slate-700">
                <div className="flex items-center gap-3">
                  <div className="h-px flex-1 bg-slate-300" />
                  <div className="inline-flex items-center px-1 py-1">
                    <span className="text-[11px] uppercase tracking-[0.18em] text-slate-700">
                      {dividerLabel(msg.content)}
                    </span>
                  </div>
                  <div className="h-px flex-1 bg-slate-300" />
                </div>
              </div>
            );
          }

          const isUser = msg.role === 'user';
          return (
            <div
              key={msg.id}
              ref={(node) => {
                messageRefs.current[msg.id] = node;
              }}
              className={`flex min-w-0 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={[
                  'min-w-0 max-w-[92%] rounded-[0.72rem] border px-3 py-2.5 text-[13px] leading-relaxed sm:max-w-[88%] sm:px-4 sm:py-3',
                  isUser
                    ? 'rounded-br-[0.3rem] border-blue-700/20 bg-slate-900 text-slate-50 shadow-[0_10px_20px_rgba(15,23,42,0.12)]'
                    : 'max-w-[100%] rounded-none border-transparent bg-transparent px-0 py-0 text-slate-900 shadow-none sm:max-w-[100%]',
                ].join(' ')}
              >
                {!isUser && showGeneratedBy && generatedByLabel(msg.generatedBy) ? (
                  <div className="mono mb-2 text-[10px] tracking-[0.12em] text-slate-500">
                    {generatedByLabel(msg.generatedBy)}
                  </div>
                ) : null}
                <p className="whitespace-pre-wrap break-words">{msg.content}</p>
              </div>
            </div>
          );
        })}
        {assistantTyping ? (
          <div className="flex min-w-0 justify-start">
            <div className="min-w-0 rounded-[0.72rem] border-transparent bg-transparent px-0 py-1 text-slate-800 shadow-none">
              <div className="flex items-center gap-1.5" aria-label="assistant typing">
                <span className="h-2 w-2 rounded-full animate-pulse bg-blue-500/60 [animation-delay:0ms]" />
                <span className="h-2 w-2 rounded-full animate-pulse bg-blue-500/60 [animation-delay:180ms]" />
                <span className="h-2 w-2 rounded-full animate-pulse bg-blue-500/60 [animation-delay:360ms]" />
              </div>
            </div>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
