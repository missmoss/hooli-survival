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
    <form onSubmit={onFormSubmit} className="mt-4 flex flex-col gap-3 sm:flex-row">
      <textarea
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={() => setIsComposing(false)}
        onKeyDown={onKeyDown}
        disabled={inputDisabled}
        placeholder={placeholder || t('input.placeholder')}
        className="mono min-h-24 min-w-0 flex-1 resize-none rounded-xl border border-black/30 bg-white px-4 py-3 text-sm text-black outline-none transition focus:border-black"
      />
      <button
        type="submit"
        disabled={sendDisabled}
        className="h-12 w-full shrink-0 rounded-xl border border-black bg-black px-3 py-2 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40 sm:h-24 sm:w-28"
      >
        {t('input.submit')}
      </button>
    </form>
  );
}
