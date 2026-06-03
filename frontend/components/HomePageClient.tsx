'use client';

import { useState } from 'react';
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

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-5xl items-center px-4 py-8 text-slate-900 sm:px-6 sm:py-14">
      <section className="relative w-full overflow-hidden rounded-[0.9rem] border border-slate-300/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,248,251,0.95))] p-5 shadow-[0_14px_32px_rgba(15,23,42,0.05)] backdrop-blur-sm sm:p-8 md:p-12">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.14),transparent_26%),linear-gradient(180deg,rgba(255,255,255,0.34),transparent_34%)]" />
        <div className="relative">
          <p className="mono text-xs uppercase tracking-[0.22em] text-slate-500">
            Corporate Survival Simulator
          </p>
          <h1 className="mt-3 text-4xl font-semibold leading-tight text-slate-950 sm:text-5xl md:text-7xl">
            Hooli Survival
          </h1>
          <p className="mt-4 max-w-2xl text-sm text-slate-600 sm:text-base md:text-lg">
            {t('home.tagline')}
          </p>

          <div className="mt-10 max-w-xl">
            <div className="rounded-[0.75rem] border border-slate-200/90 bg-white/88 p-5 shadow-[0_8px_18px_rgba(15,23,42,0.03)] sm:p-6">
              <div className="max-w-md">
                <label
                  htmlFor="player-name"
                  className="mono mb-2 block text-xs uppercase tracking-[0.12em] text-slate-500"
                >
                  {t('home.playerNameLabel')}
                </label>
                <input
                  id="player-name"
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  maxLength={24}
                  placeholder={t('home.playerNamePlaceholder')}
                  className="w-full rounded-[0.65rem] border border-slate-300 bg-white px-4 py-2 text-sm text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] outline-none transition focus:border-blue-500"
                />
              </div>

              <div className="mt-6 flex flex-wrap items-center gap-3">
                <span className="mono text-xs uppercase tracking-[0.12em] text-slate-500">
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
                        selected
                          ? 'border-blue-600 bg-blue-600 text-white'
                          : 'border-slate-300 bg-white text-slate-700 hover:border-slate-500',
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
                  className="rounded-[0.72rem] border border-blue-600 bg-blue-600 px-4 py-2 text-[13px] text-white shadow-[0_8px_18px_rgba(59,130,246,0.12)] transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400"
                >
                  {loading ? t('home.creating') : t('home.startGame')}
                </button>
                {devMode ? (
                  <>
                    <button
                      onClick={() => void startPerfReviewFixture('regular')}
                      disabled={loading}
                      className="rounded-[0.9rem] border border-slate-300 bg-white px-4 py-2.5 text-[13px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                    >
                      {t('home.devRegular')}
                    </button>
                    <button
                      onClick={() => void startPerfReviewFixture('promo')}
                      disabled={loading}
                      className="rounded-[0.9rem] border border-slate-300 bg-white px-4 py-2.5 text-[13px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                    >
                      {t('home.devPromo')}
                    </button>
                    <button
                      onClick={() => void startPerfReviewFixture('pip')}
                      disabled={loading}
                      className="rounded-[0.9rem] border border-slate-300 bg-white px-4 py-2.5 text-[13px] text-slate-700 transition hover:border-slate-500 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
                    >
                      {t('home.devPip')}
                    </button>
                  </>
                ) : null}
                <span className="mono text-xs text-slate-500">
                  {t('home.sessionMeta')} • {locale}
                </span>
              </div>
            </div>
          </div>

          {error ? <p className="mt-4 text-sm text-rose-700">{error}</p> : null}
        </div>
      </section>
    </main>
  );
}
