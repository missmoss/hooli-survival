'use client';

import { FormEvent, KeyboardEvent, useState } from 'react';

import { useI18n } from '@/lib/i18n';

type Props = {
  disabled: boolean;
  onSubmit: (message: string) => Promise<void>;
  onEmptySubmit?: () => Promise<void>;
  placeholder?: string;
  inputRef?: React.RefObject<HTMLTextAreaElement | null>;
  theme?: 'default' | 'editorial';
};

function PaperPlaneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-none stroke-current stroke-[1.8]">
      <path d="M21 3L10 14" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 3L14 21L10 14L3 10L21 3Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function InputBar({ disabled, onSubmit, onEmptySubmit, placeholder, inputRef, theme = 'default' }: Props) {
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
      className={[
        'mt-3 flex flex-col gap-3 pt-3 pb-[calc(env(safe-area-inset-bottom)+0.25rem)] sm:mt-4 sm:pt-4',
        theme === 'editorial'
          ? 'bg-transparent'
          : 'border-t border-black/10 bg-[linear-gradient(180deg,rgba(246,246,246,0),rgba(246,246,246,0.92)_20%,rgba(246,246,246,0.98))] sm:flex-row',
        theme === 'editorial' ? 'sm:grid sm:grid-cols-[minmax(0,1fr)_auto] sm:items-stretch' : '',
      ].join(' ')}
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
        className={[
          'mono min-h-[4.25rem] min-w-0 resize-none rounded-[0.58rem] px-3.5 py-3 text-[13px] outline-none transition sm:min-h-[4.5rem]',
          theme === 'editorial'
            ? 'flex-1 border border-slate-300/90 bg-white text-slate-950 shadow-none focus:border-slate-400'
            : 'flex-1 border border-black/30 bg-white text-black focus:border-black',
        ].join(' ')}
      />
      <button
        type="submit"
        disabled={sendDisabled}
        className={[
          'shrink-0 rounded-[0.58rem] px-3 py-2 text-[12px] transition disabled:cursor-not-allowed',
          theme === 'editorial'
            ? 'flex items-center justify-center gap-2 border border-blue-700 bg-blue-700 text-white shadow-[0_10px_22px_rgba(29,78,216,0.18)] hover:bg-blue-800 disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400 sm:h-auto sm:w-[92px]'
            : 'h-12 w-full border border-black bg-black text-white hover:bg-white hover:text-black disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40 sm:h-24 sm:w-28',
        ].join(' ')}
      >
        {theme === 'editorial' ? <PaperPlaneIcon /> : null}
        {t('input.submit')}
      </button>
    </form>
  );
}
