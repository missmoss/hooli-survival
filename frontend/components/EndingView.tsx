'use client';

import { type EndingPayload } from '@/lib/api';
import { SITE_URL } from '@/lib/config';
import { buildEndingShareUrls, resolveEndingPayload } from '@/lib/ending';
import { useI18n } from '@/lib/i18n';

const BUILD_POST_URL = 'https://clairetsao.substack.com/p/building-hooli-survival-software?r=w4jh';
const GITHUB_URL = 'https://github.com/missmoss/hooli-survival';

type Props = {
  ending: EndingPayload | null | undefined;
  stats?: Record<string, number> | null;
  onRestart: () => void;
};

const STAT_KEYS = ['tech', 'visibility', 'affinity', 'pip_potential'] as const;

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

function statTone(key: (typeof STAT_KEYS)[number]): string {
  const tones: Record<(typeof STAT_KEYS)[number], string> = {
    tech: 'bg-blue-500',
    visibility: 'bg-sky-500',
    affinity: 'bg-cyan-500',
    pip_potential: 'bg-slate-700',
  };
  return tones[key];
}

export default function EndingView({ ending, stats, onRestart }: Props) {
  const { locale, t } = useI18n();
  const resolved = resolveEndingPayload(ending);
  const snapshot = Object.keys(resolved.end_state.stats_snapshot || {}).length > 0
    ? resolved.end_state.stats_snapshot
    : stats || {};
  const hasStats = STAT_KEYS.some((key) => typeof snapshot[key] === 'number');
  const shareUrls = buildEndingShareUrls(resolved, locale, SITE_URL);

  return (
    <section className="relative mt-3 overflow-hidden rounded-[0.8rem] border border-slate-300/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(242,246,251,0.95))] p-4 shadow-[0_12px_28px_rgba(15,23,42,0.045)] sm:mt-4 sm:p-5">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.12),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.24),transparent_34%)]" />

      <div className="relative space-y-4">
        <div className="rounded-[0.68rem] border border-slate-200 bg-white/84 p-4 shadow-[0_6px_14px_rgba(15,23,42,0.025)]">
          <div className="mono inline-flex rounded-full border border-slate-200 bg-white/80 px-2.5 py-1 text-[11px] tracking-[0.18em] text-slate-500">
            {t('game.ending.eyebrow')}
          </div>
          <h2 className="mt-3 max-w-2xl text-[1.25rem] font-semibold tracking-[-0.02em] text-slate-950 sm:text-[1.45rem]">
            {t(resolved.title_key)}
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-600">
            {t(resolved.body_key)}
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
          {hasStats ? (
            <div className="p-2 sm:p-3">
              <div className="mono text-[11px] tracking-[0.14em] text-slate-400">{t('game.ending.statsTitle')}</div>
              <div className="mt-3 space-y-3 text-xs text-slate-700">
                {STAT_KEYS.map((key) => (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500">
                        {statLabel(locale, key)}
                      </span>
                      <span className="mono text-[11px] text-slate-700">{snapshot[key] ?? 0}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`${statTone(key)} h-full rounded-full`}
                        style={{ width: `${Math.max(0, Math.min(10, snapshot[key] ?? 0)) * 10}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="p-2 sm:p-3">
            <div className="mt-3 flex flex-col gap-2">
              {resolved.actions.restart ? (
                <button
                  onClick={onRestart}
                  className="mono rounded-[0.75rem] border border-blue-600 bg-blue-600 px-3 py-2 text-[12px] text-white transition hover:bg-blue-700"
                >
                  {t('game.ending.actions.restart')}
                </button>
              ) : null}
              <a
                href={BUILD_POST_URL}
                target="_blank"
                rel="noreferrer"
                className="mono rounded-[0.75rem] border border-slate-300 bg-white px-3 py-2 text-[12px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50"
              >
                {t('game.ending.actions.readBuildPost')}
              </a>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
                className="mono rounded-[0.75rem] border border-slate-300 bg-white px-3 py-2 text-[12px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50"
              >
                {t('game.ending.actions.viewGithub')}
              </a>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              {[
                { href: shareUrls.x, domain: 'x.com', label: 'X' },
                { href: shareUrls.threads, domain: 'threads.net', label: 'Threads' },
                { href: shareUrls.facebook, domain: 'facebook.com', label: 'Facebook' },
              ].map(({ href, domain, label }) => (
                <a
                  key={domain}
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  title={label}
                  className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white opacity-75 transition hover:opacity-100"
                >
                  <img
                    src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
                    width={14}
                    height={14}
                    alt={label}
                  />
                </a>
              ))}
            </div>
          </div>
        </div>

        <div className="p-2 sm:p-3">
          <p className="text-base font-semibold leading-snug text-slate-950">{resolved.end_state.headline}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{resolved.end_state.share_summary}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div>
              <div className="mono text-[11px] tracking-[0.14em] text-slate-500">{t('game.ending.achievement')}</div>
              <p className="mt-2 text-sm leading-relaxed text-slate-800">{resolved.end_state.achievement_line}</p>
            </div>
            <div>
              <div className="mono text-[11px] tracking-[0.14em] text-slate-500">{t('game.ending.topCase')}</div>
              <p className="mt-2 text-sm font-semibold text-slate-900">{resolved.end_state.top_case_label}</p>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{resolved.end_state.top_case_summary}</p>
            </div>
          </div>
        </div>

        {resolved.panels.scene_recap ? (
          <div className="p-2 sm:p-3">
            <div className="mono text-[11px] tracking-[0.14em] text-slate-400">{t('game.ending.recapTitle')}</div>
            <p className="mt-2 text-sm text-slate-600">{t('game.ending.emptyPanel')}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
