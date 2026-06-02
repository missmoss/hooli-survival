'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

import { DevPerfReviewScenario, createSession, devCreatePerfReviewFixture } from '@/lib/api';
import { Locale, useI18n } from '@/lib/i18n';

export default function HomePageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { locale, setLocale, t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [playerName, setPlayerName] = useState('');

  const devMode = searchParams.get('dev') === 'true';
  const editorialTheme = searchParams.get('theme') === 'editorial';

  function describeRequestError(err: unknown, fallback: string): string {
    if (err instanceof Error && err.message === 'Failed to fetch') {
      return 'Failed to fetch. Check that the backend is running and NEXT_PUBLIC_API_URL points to the right host.';
    }
    return err instanceof Error ? err.message : fallback;
  }

  function buildGameRoute(sessionId: string, overrides?: Record<string, string | null>): string {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(overrides || {}).forEach(([key, value]) => {
      if (value === null) {
        params.delete(key);
        return;
      }
      params.set(key, value);
    });
    const query = params.toString();
    return query ? `/game/${sessionId}?${query}` : `/game/${sessionId}`;
  }

  async function startGame() {
    setLoading(true);
    setError(null);
    try {
      const created = await createSession(playerName, locale);
      sessionStorage.setItem(`hooli:session:${created.session_id}`, JSON.stringify(created));
      router.push(buildGameRoute(created.session_id));
    } catch (err) {
      setError(describeRequestError(err, 'Unable to create session'));
    } finally {
      setLoading(false);
    }
  }

  async function startPerfReviewFixture(scenario: DevPerfReviewScenario) {
    setLoading(true);
    setError(null);
    try {
      const created = await devCreatePerfReviewFixture(playerName, scenario, locale);
      sessionStorage.setItem(`hooli:session:${created.session_id}`, JSON.stringify(created));
      router.push(buildGameRoute(created.session_id, { dev: 'true' }));
    } catch (err) {
      setError(describeRequestError(err, 'Unable to create perf review fixture session'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }
    const nextTheme = editorialTheme ? 'editorial' : 'default';
    document.documentElement.dataset.uiTheme = nextTheme;
    document.body.dataset.uiTheme = nextTheme;
    return () => {
      document.documentElement.dataset.uiTheme = 'default';
      document.body.dataset.uiTheme = 'default';
    };
  }, [editorialTheme]);

  return (
    <main
      className={[
        'mx-auto flex min-h-[100dvh] w-full max-w-5xl items-center px-4 py-8 sm:px-6 sm:py-14',
        editorialTheme ? 'text-slate-900' : '',
      ].join(' ')}
    >
      <section
        className={[
          'relative w-full overflow-hidden rounded-[1.75rem] p-5 backdrop-blur-sm sm:rounded-3xl sm:p-8 md:p-12',
          editorialTheme
            ? 'rounded-[0.9rem] border border-slate-300/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,248,251,0.95))] shadow-[0_14px_32px_rgba(15,23,42,0.05)] sm:rounded-[0.9rem] md:rounded-[0.9rem]'
            : 'border border-black/30 bg-white/80 shadow-frame',
        ].join(' ')}
      >
        {editorialTheme ? (
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.14),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.34),transparent_34%)]" />
        ) : null}
        <div className="relative">
          <p className={['mono text-xs uppercase tracking-[0.22em]', editorialTheme ? 'text-slate-500' : 'text-black/55'].join(' ')}>
            Corporate Survival Simulator
          </p>
          <h1 className={['mt-3 text-4xl font-semibold leading-tight sm:text-5xl md:text-7xl', editorialTheme ? 'text-slate-950' : 'text-black'].join(' ')}>
            Hooli Survival
          </h1>
          <p className={['mt-4 max-w-2xl text-sm sm:text-base md:text-lg', editorialTheme ? 'text-slate-600' : 'text-black/75'].join(' ')}>
            {t('home.tagline')}
          </p>

          <div className={editorialTheme ? 'mt-10 max-w-xl' : ''}>
            <div className={editorialTheme ? 'rounded-[0.75rem] border border-slate-200/90 bg-white/88 p-5 shadow-[0_8px_18px_rgba(15,23,42,0.03)] sm:p-6' : ''}>
              <div className="max-w-md">
                <label
                  htmlFor="player-name"
                  className={['mono mb-2 block text-xs uppercase tracking-[0.12em]', editorialTheme ? 'text-slate-500' : 'text-black/60'].join(' ')}
                >
                  {t('home.playerNameLabel')}
                </label>
                <input
                  id="player-name"
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  maxLength={24}
                  placeholder={t('home.playerNamePlaceholder')}
                  className={[
                    'w-full rounded-[0.65rem] px-4 py-2 text-sm outline-none transition',
                    editorialTheme
                      ? 'border border-slate-300 bg-white text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] focus:border-blue-500'
                      : 'border border-black/30 bg-white text-black focus:border-black',
                  ].join(' ')}
                />
              </div>

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <span className={['mono text-xs uppercase tracking-[0.12em]', editorialTheme ? 'text-slate-500' : 'text-black/60'].join(' ')}>
                  {t('home.language')}
                </span>
                {([
                  ['en', t('home.english')],
                  ['zh-Hant', t('home.traditionalChinese')],
                ] as const).map(([value, label]) => {
                  const selected = locale === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setLocale(value as Locale)}
                      className={[
                        'rounded-full border px-3 py-1 text-sm transition',
                        editorialTheme
                          ? selected
                            ? 'border-blue-600 bg-blue-600 text-white'
                            : 'border-slate-300 bg-white text-slate-700 hover:border-slate-500'
                          : selected
                            ? 'border-black bg-black text-white'
                            : 'border-black/30 bg-white text-black hover:border-black',
                      ].join(' ')}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>

              <div className="mt-6 flex flex-col items-start gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-4">
                <button
                  onClick={startGame}
                  disabled={loading}
                  className={[
                    'rounded-[0.72rem] px-4 py-2 text-[13px] transition disabled:cursor-not-allowed',
                    editorialTheme
                      ? 'border border-blue-600 bg-blue-600 text-white shadow-[0_8px_18px_rgba(59,130,246,0.12)] hover:bg-blue-700 disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400'
                      : 'border border-black bg-black text-white hover:bg-white hover:text-black disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
                  ].join(' ')}
                >
                  {loading ? t('home.creating') : t('home.startGame')}
                </button>
                {devMode ? (
                  <>
                    <button
                      onClick={() => void startPerfReviewFixture('regular')}
                      disabled={loading}
                      className={[
                        'rounded-[0.9rem] px-4 py-2.5 text-[13px] transition disabled:cursor-not-allowed',
                        editorialTheme
                          ? 'border border-slate-300 bg-white text-slate-700 hover:border-slate-500 hover:bg-slate-50 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400'
                          : 'border border-black/60 bg-white text-black hover:bg-black hover:text-white disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
                      ].join(' ')}
                    >
                      {t('home.devRegular')}
                    </button>
                    <button
                      onClick={() => void startPerfReviewFixture('promo')}
                      disabled={loading}
                      className={[
                        'rounded-[0.9rem] px-4 py-2.5 text-[13px] transition disabled:cursor-not-allowed',
                        editorialTheme
                          ? 'border border-slate-300 bg-white text-slate-700 hover:border-slate-500 hover:bg-slate-50 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400'
                          : 'border border-black/60 bg-white text-black hover:bg-black hover:text-white disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
                      ].join(' ')}
                    >
                      {t('home.devPromo')}
                    </button>
                    <button
                      onClick={() => void startPerfReviewFixture('pip')}
                      disabled={loading}
                      className={[
                        'rounded-[0.9rem] px-4 py-2.5 text-[13px] transition disabled:cursor-not-allowed',
                        editorialTheme
                          ? 'border border-slate-300 bg-white text-slate-700 hover:border-slate-500 hover:bg-slate-50 disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400'
                          : 'border border-black/60 bg-white text-black hover:bg-black hover:text-white disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
                      ].join(' ')}
                    >
                      {t('home.devPip')}
                    </button>
                  </>
                ) : null}
                <span className={['mono text-xs', editorialTheme ? 'text-slate-500' : 'text-black/55'].join(' ')}>
                  {t('home.sessionMeta')} • {locale}
                </span>
              </div>
            </div>
          </div>

          {error ? <p className={['mt-4 text-sm', editorialTheme ? 'text-rose-700' : 'text-black/70'].join(' ')}>{error}</p> : null}
        </div>
      </section>
    </main>
  );
}
