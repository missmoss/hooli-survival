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

  async function startGame() {
    setLoading(true);
    setError(null);
    try {
      const created = await createSession(playerName, locale);
      sessionStorage.setItem(`hooli:session:${created.session_id}`, JSON.stringify(created));
      const query = devMode ? '?dev=true' : '';
      router.push(`/game/${created.session_id}${query}`);
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
      router.push(`/game/${created.session_id}?dev=true`);
    } catch (err) {
      setError(describeRequestError(err, 'Unable to create perf review fixture session'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl items-center px-6 py-14">
      <section className="w-full rounded-3xl border border-black/30 bg-white/80 p-8 shadow-frame backdrop-blur-sm md:p-12">
        <p className="mono text-xs uppercase tracking-[0.22em] text-black/55">Corporate Survival Simulator</p>
        <h1 className="mt-3 text-5xl font-semibold leading-tight text-black md:text-7xl">Hooli Survival</h1>
        <p className="mt-5 max-w-2xl text-base text-black/75 md:text-lg">
          {t('home.tagline')}
        </p>

        <div className="mt-8 max-w-md">
          <label htmlFor="player-name" className="mono mb-2 block text-xs uppercase tracking-[0.12em] text-black/60">
            {t('home.playerNameLabel')}
          </label>
          <input
            id="player-name"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            maxLength={24}
            placeholder={t('home.playerNamePlaceholder')}
            className="w-full rounded-xl border border-black/30 bg-white px-4 py-2 text-sm text-black outline-none transition focus:border-black"
          />
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <span className="mono text-xs uppercase tracking-[0.12em] text-black/60">{t('home.language')}</span>
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
                  selected ? 'border-black bg-black text-white' : 'border-black/30 bg-white text-black hover:border-black',
                ].join(' ')}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <button
            onClick={startGame}
            disabled={loading}
            className="rounded-xl border border-black bg-black px-6 py-3 text-base text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
          >
            {loading ? t('home.creating') : t('home.startGame')}
          </button>
          {devMode ? (
            <>
              <button
                onClick={() => void startPerfReviewFixture('regular')}
                disabled={loading}
                className="rounded-xl border border-black/60 bg-white px-4 py-3 text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
              >
                {t('home.devRegular')}
              </button>
              <button
                onClick={() => void startPerfReviewFixture('promo')}
                disabled={loading}
                className="rounded-xl border border-black/60 bg-white px-4 py-3 text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
              >
                {t('home.devPromo')}
              </button>
              <button
                onClick={() => void startPerfReviewFixture('pip')}
                disabled={loading}
                className="rounded-xl border border-black/60 bg-white px-4 py-3 text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
              >
                {t('home.devPip')}
              </button>
            </>
          ) : null}
          <span className="mono text-xs text-black/55">
            {t('home.sessionMeta')} • {locale}
          </span>
        </div>

        {error ? <p className="mt-4 text-sm text-black/70">{error}</p> : null}
      </section>
    </main>
  );
}
