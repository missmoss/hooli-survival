'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

import en from '@/locales/en';
import zhHant from '@/locales/zh-Hant';

export type Locale = 'en' | 'zh-Hant';

const STORAGE_KEY = 'hooli:locale';

const messages = {
  en,
  'zh-Hant': zhHant,
} as const;

type MessageTree = {
  [key: string]: string | MessageTree;
};
type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function normalizeLocale(locale: string | null | undefined): Locale {
  const raw = (locale || '').toLowerCase();
  if (raw.startsWith('zh')) {
    return 'zh-Hant';
  }
  return 'en';
}

function detectLocale(): Locale {
  if (typeof window === 'undefined') {
    return 'en';
  }
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored) {
    return normalizeLocale(stored);
  }
  return normalizeLocale(window.navigator.language);
}

function readKey(tree: MessageTree, key: string): string {
  const value = key.split('.').reduce<unknown>((current, part) => {
    if (current && typeof current === 'object' && part in (current as Record<string, unknown>)) {
      return (current as Record<string, unknown>)[part];
    }
    return undefined;
  }, tree);
  return typeof value === 'string' ? value : key;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('en');

  useEffect(() => {
    const detected = detectLocale();
    setLocaleState(detected);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, locale);
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18nContextValue>(() => {
    return {
      locale,
      setLocale: (nextLocale: Locale) => setLocaleState(nextLocale),
      t: (key: string) => readKey(messages[locale], key),
    };
  }, [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used inside I18nProvider');
  }
  return context;
}
