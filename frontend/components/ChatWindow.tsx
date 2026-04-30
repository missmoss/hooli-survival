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

export default function ChatWindow({ messages, assistantTyping = false, showGeneratedBy = false }: Props) {
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const messageRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (assistantTyping) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
      return;
    }
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage) {
      return;
    }
    if (lastMessage.role === 'assistant') {
      messageRefs.current[lastMessage.id]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto rounded-2xl border border-black/30 bg-white/85 p-4 shadow-frame backdrop-blur-sm">
      <div className="space-y-4">
        {messages.map((msg) => {
          if (msg.role === 'divider') {
            return (
              <div key={msg.id} className="py-2 text-center text-xs tracking-[0.2em] text-black/55 mono">
                {msg.content}
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
                  'min-w-0 max-w-[85%] rounded-xl border px-4 py-3 text-sm leading-relaxed',
                  isUser
                    ? 'border-black/40 bg-black text-white mono'
                    : 'border-black/20 bg-white text-black',
                ].join(' ')}
              >
                {!isUser && showGeneratedBy && generatedByLabel(msg.generatedBy) ? (
                  <div className="mono mb-2 text-[10px] tracking-[0.12em] text-black/45">
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
            <div className="min-w-0 rounded-xl border border-black/20 bg-white px-4 py-3 text-black shadow-sm">
              <div className="flex items-center gap-1.5" aria-label="assistant typing">
                <span className="h-2 w-2 rounded-full bg-black/60 animate-pulse [animation-delay:0ms]" />
                <span className="h-2 w-2 rounded-full bg-black/60 animate-pulse [animation-delay:180ms]" />
                <span className="h-2 w-2 rounded-full bg-black/60 animate-pulse [animation-delay:360ms]" />
              </div>
            </div>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
