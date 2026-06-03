'use client';

import { FormEvent, KeyboardEvent, useState } from 'react';

import { useI18n } from '@/lib/i18n';

type Props = {
  disabled: boolean;
  onSubmit: (message: string) => Promise<void>;
  onEmptySubmit?: () => Promise<void>;
  placeholder?: string;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
};

function PaperPlaneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-none stroke-current stroke-[1.8]">
      <path d="M21 3L10 14" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 3L14 21L10 14L3 10L21 3Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function InputBar({ disabled, onSubmit, onEmptySubmit, placeholder, inputRef }: Props) {
  const { t } = useI18n();
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [isComposing, setIsComposing] = useState(false);

  async function submit() {
    const text = value.trim();
    if (disabled || submitting) {
      return;
    }
    setSubmitting(true);
    try {
      if (!text) {
        if (!onEmptySubmit) {
          return;
        }
        await onEmptySubmit();
        return;
      }
      setValue('');
      await onSubmit(text);
    } finally {
      setSubmitting(false);
    }
  }

  async function onFormSubmit(e: FormEvent) {
    e.preventDefault();
    await submit();
  }

  async function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    const imeComposing = isComposing || e.nativeEvent.isComposing || e.keyCode === 229;
    if (imeComposing) {
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      await submit();
    }
  }

  const inputDisabled = disabled;
  const sendDisabled = disabled || submitting;

  return (
    <form
      onSubmit={onFormSubmit}
      className="mt-3 flex flex-col gap-3 bg-transparent pt-3 pb-[calc(env(safe-area-inset-bottom)+0.25rem)] sm:mt-4 sm:grid sm:grid-cols-[minmax(0,1fr)_auto] sm:items-stretch sm:pt-4"
    >
      <textarea
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={() => setIsComposing(false)}
        onKeyDown={onKeyDown}
        disabled={inputDisabled}
        placeholder={placeholder || t('input.placeholder')}
        className="mono min-h-[4.25rem] min-w-0 flex-1 resize-none rounded-[0.58rem] border border-slate-300/90 bg-white px-3.5 py-3 text-[13px] text-slate-950 shadow-none outline-none transition focus:border-slate-400 sm:min-h-[4.5rem]"
      />
      <button
        type="submit"
        disabled={sendDisabled}
        className="flex shrink-0 items-center justify-center gap-2 rounded-[0.58rem] border border-blue-700 bg-blue-700 px-3 py-2 text-[12px] text-white shadow-[0_10px_22px_rgba(29,78,216,0.18)] transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400 sm:h-auto sm:w-[92px]"
      >
        <PaperPlaneIcon />
        {t('input.submit')}
      </button>
    </form>
  );
}
