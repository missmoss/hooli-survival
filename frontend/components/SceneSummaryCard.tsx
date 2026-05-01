'use client';

import { LatestEval } from '@/lib/api';
import { Locale, useI18n } from '@/lib/i18n';

type Props = {
  evaluation: LatestEval;
  onContinue: () => void;
};

const DELTA_KEYS = ['tech', 'visibility', 'affinity', 'pip_potential'] as const;

const HEADLINES: Record<Locale, Record<'good' | 'neutral' | 'bad', string[]>> = {
  en: {
    good: ['Nice save.', 'Management noticed.', 'You looked expensive in a good way.'],
    neutral: ['You survived. Barely.', 'No one escalated it. Yet.', 'That could have gone worse.'],
    bad: ['That got messy.', 'Not your cleanest moment.', 'Someone is updating a spreadsheet about this.'],
  },
  'zh-Hant': {
    good: ['收得不錯。', '管理層有看到。', '這次看起來像是高成本人才。'],
    neutral: ['你活下來了。暫時。', '至少還沒被 escalate。', '還行，沒更糟。'],
    bad: ['這次有點亂。', '不是你最乾淨的一次。', '有人正在更新一張關於你的表。'],
  },
};

function pickHeadline(locale: Locale, evaluation: LatestEval): string {
  const rating = evaluation.rating === 'good' || evaluation.rating === 'bad' ? evaluation.rating : 'neutral';
  const candidates = HEADLINES[locale][rating];
  const score = DELTA_KEYS.reduce((total, key, index) => total + ((evaluation.delta[key] ?? 0) * (index + 2)), 0);
  return candidates[Math.abs(score) % candidates.length];
}

function deltaLabel(locale: Locale, key: string): string {
  const labels: Record<Locale, Record<string, string>> = {
    en: {
      tech: 'Tech',
      visibility: 'Visibility',
      affinity: 'Affinity',
      pip_potential: 'PIP Risk',
    },
    'zh-Hant': {
      tech: '技術',
      visibility: '能見度',
      affinity: '關係',
      pip_potential: 'PIP 風險',
    },
  };
  return labels[locale][key] || key;
}

function ratingLabel(locale: Locale, rating: string): string {
  const labels: Record<Locale, Record<string, string>> = {
    en: {
      good: 'good',
      neutral: 'neutral',
      bad: 'bad',
    },
    'zh-Hant': {
      good: '好',
      neutral: '普通',
      bad: '糟',
    },
  };
  return labels[locale][rating] || labels[locale].neutral;
}

function deltaEntries(evaluation: LatestEval, locale: Locale): string[] {
  const values = DELTA_KEYS
    .map((key) => {
      const value = Number(evaluation.delta[key] ?? 0);
      if (!value) {
        return null;
      }
      return `${value > 0 ? '+' : ''}${value} ${deltaLabel(locale, key)}`;
    })
    .filter((entry): entry is string => Boolean(entry));
  return values.length > 0 ? values : [locale === 'zh-Hant' ? '沒有數值變動' : 'No stat changes'];
}

export default function SceneSummaryCard({ evaluation, onContinue }: Props) {
  const { locale, t } = useI18n();
  const deltas = deltaEntries(evaluation, locale);

  return (
    <section className="mt-3 rounded-[1.4rem] border border-black/30 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,248,248,0.92))] p-4 shadow-frame sm:mt-4 sm:p-5">
      <div className="mono inline-flex rounded-full border border-black/20 bg-black/[0.03] px-2.5 py-1 text-[11px] tracking-[0.16em] text-black/58">
        {t('summary.eyebrow')}
      </div>
      <h2 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-black sm:text-2xl">
        {pickHeadline(locale, evaluation)}
      </h2>
      <p className="mono mt-2 text-xs tracking-[0.14em] text-black/52">
        {t('summary.rating')}: {ratingLabel(locale, evaluation.rating)}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {deltas.map((entry) => (
          <div
            key={entry}
            className="rounded-full border border-black/15 bg-black/[0.03] px-3 py-1.5 text-sm text-black/82"
          >
            {entry}
          </div>
        ))}
      </div>
      <button
        onClick={onContinue}
        className="mono mt-5 w-full rounded-xl border border-black bg-black px-4 py-3 text-sm text-white transition hover:bg-white hover:text-black sm:w-auto"
      >
        {t('summary.continue')}
      </button>
    </section>
  );
}
