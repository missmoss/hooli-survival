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
  theme?: 'default' | 'editorial';
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

function statTone(key: (typeof STAT_KEYS)[number]): string {
  const tones: Record<(typeof STAT_KEYS)[number], string> = {
    tech: 'bg-blue-500',
    visibility: 'bg-sky-500',
    affinity: 'bg-cyan-500',
    pip_potential: 'bg-slate-700',
  };
  return tones[key];
}

export default function EndingView({ ending, stats, onRestart, theme = 'default' }: Props) {
  const { locale, t } = useI18n();
  const resolved = resolveEndingPayload(ending);
  const snapshot = Object.keys(resolved.end_state.stats_snapshot || {}).length > 0
    ? resolved.end_state.stats_snapshot
    : stats || {};
  const hasStats = STAT_KEYS.some((key) => typeof snapshot[key] === 'number');
  const shareUrls = buildEndingShareUrls(resolved, locale, SITE_URL);
  const editorial = theme === 'editorial';

  return (
    <section
      className={[
        `relative mt-3 overflow-hidden rounded-[0.8rem] border p-4 sm:mt-4 sm:p-5 ${
          editorial
            ? 'border-slate-300/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(242,246,251,0.95))]'
            : resolved.containerClassName
        }`,
        editorial ? 'shadow-[0_12px_28px_rgba(15,23,42,0.045)]' : 'shadow-frame',
      ].join(' ')}
    >
      <div
        className={`pointer-events-none absolute inset-0 ${
          editorial
            ? 'bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.12),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.24),transparent_34%)]'
            : resolved.glowClassName
        }`}
      />

      <div className="relative space-y-4">
        <div className={editorial ? 'rounded-[0.68rem] border border-slate-200 bg-white/84 p-4 shadow-[0_6px_14px_rgba(15,23,42,0.025)]' : ''}>
          <div
            className={`mono inline-flex rounded-full border px-2.5 py-1 text-[11px] tracking-[0.18em] ${
              editorial ? 'border-slate-200 bg-white/80 text-slate-500' : resolved.badgeClassName
            }`}
          >
            {t('game.ending.eyebrow')}
          </div>
          <h2 className={['mt-3 max-w-2xl text-[1.25rem] font-semibold tracking-[-0.02em] sm:text-[1.45rem]', editorial ? 'text-slate-950' : 'text-black'].join(' ')}>
            {t(resolved.title_key)}
          </h2>
          <p className={['mt-3 max-w-2xl text-sm leading-relaxed', editorial ? 'text-slate-600' : 'text-black/76'].join(' ')}>
            {t(resolved.body_key)}
          </p>
        </div>

        <div className={['grid gap-3', editorial ? 'md:grid-cols-[minmax(0,1fr)_220px]' : 'md:grid-cols-2'].join(' ')}>
          {hasStats ? (
            <div className={['p-2 sm:p-3', editorial ? '' : 'rounded-[0.68rem] border border-black/10 bg-white/55'].join(' ')}>
              <div className={['mono text-[11px] tracking-[0.14em]', editorial ? 'text-slate-400' : 'text-black/55'].join(' ')}>{t('game.ending.statsTitle')}</div>
              <div className={['mt-3 space-y-3 text-xs', editorial ? 'text-slate-700' : 'mono text-black'].join(' ')}>
                {STAT_KEYS.map((key) => (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <span className={editorial ? 'text-[11px] font-medium uppercase tracking-[0.08em] text-slate-500' : ''}>
                        {statLabel(locale, key)}
                      </span>
                      <span className={editorial ? 'mono text-[11px] text-slate-700' : 'text-right'}>{snapshot[key] ?? 0}</span>
                    </div>
                    {editorial ? (
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`${statTone(key)} h-full rounded-full`}
                          style={{ width: `${Math.max(0, Math.min(10, snapshot[key] ?? 0)) * 10}%` }}
                        />
                      </div>
                    ) : (
                      <div className="grid grid-cols-[84px_1fr_24px] items-center gap-2 mono">
                        <span>{statLabel(locale, key)}</span>
                        <span>{statBar(snapshot[key] ?? 0)}</span>
                        <span className="text-right">{snapshot[key] ?? 0}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className={editorial ? 'p-2 sm:p-3' : ''}>
            <div className="mt-3 flex flex-col gap-2">
              {resolved.actions.restart ? (
                <button
                  onClick={onRestart}
                  className={editorial ? 'mono rounded-[0.75rem] border border-blue-600 bg-blue-600 px-3 py-2 text-[12px] text-white transition hover:bg-blue-700' : 'mono rounded-md border border-black bg-black px-3 py-2 text-xs text-white transition hover:bg-white hover:text-black'}
                >
                  {t('game.ending.actions.restart')}
                </button>
              ) : null}
              <a
                href={BUILD_POST_URL}
                target="_blank"
                rel="noreferrer"
                className={editorial ? 'mono rounded-[0.75rem] border border-slate-300 bg-white px-3 py-2 text-[12px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50' : 'mono rounded-md border border-black/60 bg-white/70 px-3 py-2 text-xs text-black transition hover:bg-black hover:text-white'}
              >
                {t('game.ending.actions.readBuildPost')}
              </a>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noreferrer"
                className={editorial ? 'mono rounded-[0.75rem] border border-slate-300 bg-white px-3 py-2 text-[12px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50' : 'mono rounded-md border border-black/60 bg-white/70 px-3 py-2 text-xs text-black transition hover:bg-black hover:text-white'}
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
                  className={editorial ? 'flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white opacity-75 transition hover:opacity-100' : 'flex h-6 w-6 items-center justify-center rounded-md border border-black/15 bg-white/70 opacity-60 transition hover:opacity-100'}
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

        <div className={['p-2 sm:p-3', editorial ? '' : 'rounded-[0.68rem] border border-black/10 bg-white/65'].join(' ')}>
          <p className={['text-base font-semibold leading-snug', editorial ? 'text-slate-950' : 'text-black'].join(' ')}>{resolved.end_state.headline}</p>
          <p className={['mt-2 text-sm leading-relaxed', editorial ? 'text-slate-600' : 'text-black/72'].join(' ')}>{resolved.end_state.share_summary}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className={['p-0', editorial ? '' : 'rounded-[0.62rem] border border-black/10 bg-black/[0.03] p-3'].join(' ')}>
              <div className={['mono text-[11px] tracking-[0.14em]', editorial ? 'text-slate-500' : 'text-black/50'].join(' ')}>{t('game.ending.achievement')}</div>
              <p className={['mt-2 text-sm leading-relaxed', editorial ? 'text-slate-800' : 'text-black'].join(' ')}>{resolved.end_state.achievement_line}</p>
            </div>
            <div className={['p-0', editorial ? '' : 'rounded-[0.62rem] border border-black/10 bg-black/[0.03] p-3'].join(' ')}>
              <div className={['mono text-[11px] tracking-[0.14em]', editorial ? 'text-slate-500' : 'text-black/50'].join(' ')}>{t('game.ending.topCase')}</div>
              <p className={['mt-2 text-sm font-semibold', editorial ? 'text-slate-900' : 'text-black'].join(' ')}>{resolved.end_state.top_case_label}</p>
              <p className={['mt-1 text-sm leading-relaxed', editorial ? 'text-slate-600' : 'text-black/72'].join(' ')}>{resolved.end_state.top_case_summary}</p>
            </div>
          </div>
        </div>

        {resolved.panels.scene_recap ? (
          <div className={['p-2 sm:p-3', editorial ? '' : 'rounded-[0.68rem] border border-black/10 bg-white/55'].join(' ')}>
            <div className={['mono text-[11px] tracking-[0.14em]', editorial ? 'text-slate-400' : 'text-black/55'].join(' ')}>{t('game.ending.recapTitle')}</div>
            <p className={['mt-2 text-sm', editorial ? 'text-slate-600' : 'text-black/65'].join(' ')}>{t('game.ending.emptyPanel')}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
