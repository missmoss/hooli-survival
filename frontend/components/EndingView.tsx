'use client';

import { useState } from 'react';

import { type EndingPayload } from '@/lib/api';
import { buildEndingShareText, resolveEndingPayload } from '@/lib/ending';
import { useI18n } from '@/lib/i18n';

const BUILD_POST_URL = 'https://clairetsao.substack.com/p/building-hooli-survival-software?r=w4jh';
const GITHUB_URL = 'https://github.com/missmoss/hooli-survival';

type Props = {
  ending: EndingPayload | null | undefined;
  stats?: Record<string, number> | null;
  onRestart: () => void;
};

const STAT_KEYS = ['tech', 'visibility', 'affinity', 'pip_potential'] as const;

function statBar(value: number): string {
  const clamped = Math.max(0, Math.min(10, value));
  return `${'█'.repeat(clamped)}${'░'.repeat(10 - clamped)}`;
}

function statLabel(locale: string, key: (typeof STAT_KEYS)[number]): string {
  const labels = {
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
  } as const;
  return labels[locale as keyof typeof labels]?.[key] || key;
}

export default function EndingView({ ending, stats, onRestart }: Props) {
  const { locale, t } = useI18n();
  const resolved = resolveEndingPayload(ending);
  const [shareFeedback, setShareFeedback] = useState('');
  const snapshot = Object.keys(resolved.end_state.stats_snapshot || {}).length > 0
    ? resolved.end_state.stats_snapshot
    : stats || {};
  const hasStats = STAT_KEYS.some((key) => typeof snapshot[key] === 'number');

  async function handleShare() {
    const url = typeof window !== 'undefined' ? new URL('/', window.location.origin).toString() : '';
    const text = buildEndingShareText(resolved, locale, url);
    try {
      if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
        await navigator.share({
          title: resolved.end_state.headline,
          text,
          url,
        });
      } else if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        throw new Error('share unavailable');
      }
      setShareFeedback(t('game.ending.copied'));
    } catch {
      setShareFeedback(t('game.ending.shareFailed'));
    }
  }

  return (
    <section className={`relative mt-3 overflow-hidden rounded-[1.5rem] border p-4 shadow-frame sm:mt-4 sm:rounded-[1.75rem] sm:p-5 ${resolved.containerClassName}`}>
      <div className={`pointer-events-none absolute inset-0 ${resolved.glowClassName}`} />
      <div className="relative">
        <div className={`mono inline-flex rounded-full border px-2.5 py-1 text-[11px] tracking-[0.18em] ${resolved.badgeClassName}`}>
          {t('game.ending.eyebrow')}
        </div>
        <h2 className="mt-3 max-w-2xl text-[1.25rem] font-semibold tracking-[-0.02em] text-black sm:text-[1.45rem]">{t(resolved.title_key)}</h2>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-black/76">{t(resolved.body_key)}</p>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {hasStats ? (
            <div className="rounded-2xl border border-black/10 bg-white/55 p-4">
              <div className="mono text-[11px] tracking-[0.14em] text-black/55">{t('game.ending.statsTitle')}</div>
              <div className="mt-3 space-y-2 mono text-xs text-black">
                {STAT_KEYS.map((key) => (
                  <div key={key} className="grid grid-cols-[84px_1fr_24px] items-center gap-2">
                    <span>{statLabel(locale, key)}</span>
                    <span>{statBar(snapshot[key] ?? 0)}</span>
                    <span className="text-right">{snapshot[key] ?? 0}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {resolved.panels.scene_recap ? (
            <div className="rounded-2xl border border-black/10 bg-white/55 p-4">
              <div className="mono text-[11px] tracking-[0.14em] text-black/55">{t('game.ending.recapTitle')}</div>
              <p className="mt-2 text-sm text-black/65">{t('game.ending.emptyPanel')}</p>
            </div>
          ) : null}
        </div>

        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          {resolved.actions.restart ? (
            <button
              onClick={onRestart}
              className="mono rounded-md border border-black bg-black px-3 py-2 text-xs text-white transition hover:bg-white hover:text-black"
            >
              {t('game.ending.actions.restart')}
            </button>
          ) : null}
          {resolved.actions.share ? (
            <button
              onClick={() => void handleShare()}
              className="mono rounded-md border border-black/60 bg-white/70 px-3 py-2 text-xs text-black transition hover:bg-black hover:text-white"
            >
              {t('game.ending.actions.share')}
            </button>
          ) : null}
          <a
            href={BUILD_POST_URL}
            target="_blank"
            rel="noreferrer"
            className="mono rounded-md border border-black/60 bg-white/70 px-3 py-2 text-xs text-black transition hover:bg-black hover:text-white"
          >
            {t('game.ending.actions.readBuildPost')}
          </a>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noreferrer"
            className="mono rounded-md border border-black/60 bg-white/70 px-3 py-2 text-xs text-black transition hover:bg-black hover:text-white"
          >
            {t('game.ending.actions.viewGithub')}
          </a>
        </div>
        {shareFeedback ? <p className="mt-2 text-xs text-black/58 mono">{shareFeedback}</p> : null}

        <div className="mt-5 rounded-[1.25rem] border border-black/10 bg-white/65 p-3.5 sm:rounded-[1.4rem] sm:p-4">
          <div className="mono text-[11px] tracking-[0.16em] text-black/55">{t('game.ending.shareTitle')}</div>
          <p className="mt-2 text-base font-semibold leading-snug text-black">{resolved.end_state.headline}</p>
          <p className="mt-2 text-sm leading-relaxed text-black/72">{resolved.end_state.share_summary}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-black/10 bg-black/[0.03] p-3">
              <div className="mono text-[11px] tracking-[0.14em] text-black/50">{t('game.ending.achievement')}</div>
              <p className="mt-2 text-sm leading-relaxed text-black">{resolved.end_state.achievement_line}</p>
            </div>
            <div className="rounded-2xl border border-black/10 bg-black/[0.03] p-3">
              <div className="mono text-[11px] tracking-[0.14em] text-black/50">{t('game.ending.topCase')}</div>
              <p className="mt-2 text-sm font-semibold text-black">{resolved.end_state.top_case_label}</p>
              <p className="mt-1 text-sm leading-relaxed text-black/72">{resolved.end_state.top_case_summary}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
