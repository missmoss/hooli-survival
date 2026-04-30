'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';

import ChatWindow, { ChatMessage } from '@/components/ChatWindow';
import EndingView from '@/components/EndingView';
import InputBar from '@/components/InputBar';
import SceneTransition from '@/components/SceneTransition';
import StatPanel from '@/components/StatPanel';
import { CharacterCard, EndingPayload, GeneratedBy, StoryOption, getNextScene, getSession, sendTurn } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

function uid() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function GamePage() {
  const { locale, setLocale, t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const devMode = searchParams.get('dev') === 'true';

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [options, setOptions] = useState<StoryOption[]>([]);
  const [currentSceneId, setCurrentSceneId] = useState('');
  const [characters, setCharacters] = useState<{
    manager: CharacterCard;
    buddy: CharacterCard;
    team_members: CharacterCard[];
  } | null>(null);
  const [state, setState] = useState<Record<string, number> | null>(null);
  const [latestEval, setLatestEval] = useState<{
    scene_type: 'project' | 'event';
    scene_id: string;
    rating: string;
    reason: string | null;
    delta: Record<string, number>;
  } | null>(null);
  const [round, setRound] = useState(0);
  const [maxRounds, setMaxRounds] = useState(0);
  const [status, setStatus] = useState('active');
  const [ending, setEnding] = useState<EndingPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [settling, setSettling] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedPerfOptions, setSelectedPerfOptions] = useState<string[]>([]);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollLockRef = useRef(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  function assistantMessage(content: string, generatedBy?: GeneratedBy): ChatMessage {
    return { id: uid(), role: 'assistant', content, generatedBy: devMode ? generatedBy || null : null };
  }

  function clearPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function refreshSession() {
    const session = await getSession(sessionId);
    if (session.locale !== locale) {
      setLocale(session.locale);
    }
    setState(session.state);
    setCharacters(session.characters);
    setCurrentSceneId(session.current_scene_id);
    setRound(session.round);
    setMaxRounds(session.max_rounds);
    setStatus(session.status);
    setEnding(session.ending);
    setLatestEval(session.latest_eval);
    setOptions(session.current_options || []);

    setMessages((prev) => {
      if (prev.length === 0 && session.current_opening_text) {
        return [assistantMessage(session.current_opening_text, session.current_generated_by)];
      }
      if (!devMode || !session.current_opening_text || !session.current_generated_by) {
        return prev;
      }
      return prev.map((msg, index) => {
        if (
          index === 0 &&
          msg.role === 'assistant' &&
          msg.content === session.current_opening_text &&
          !msg.generatedBy
        ) {
          return { ...msg, generatedBy: session.current_generated_by };
        }
        return msg;
      });
    });
  }

  async function checkNextScene(): Promise<boolean> {
    if (pollLockRef.current) {
      return false;
    }
    pollLockRef.current = true;
    try {
      const next = await getNextScene(sessionId);
      if (next.ready) {
        clearPolling();
        setSettling(false);
        setMessages((prev) => [
          ...prev,
          { id: uid(), role: 'divider', content: t('game.newScene') },
          assistantMessage(next.text, next.generated_by),
        ]);
        setCurrentSceneId(next.scene_id);
        setOptions(next.options || []);
        await refreshSession();
        return true;
      }
    } catch {
      // Keep polling on transient failures.
    } finally {
      pollLockRef.current = false;
    }
    return false;
  }

  function startPolling(auto = false) {
    setSettling(true);
    clearPolling();
    if (auto) {
      pollRef.current = setInterval(() => {
        void checkNextScene();
      }, 1000);
      void checkNextScene();
    }
  }

  function restartGame() {
    sessionStorage.removeItem(`hooli:session:${sessionId}`);
    router.push('/?dev=true');
  }

  useEffect(() => {
    let mounted = true;

    async function init() {
      setError(null);
      try {
        const raw = sessionStorage.getItem(`hooli:session:${sessionId}`);
        if (raw) {
          const created = JSON.parse(raw) as { text?: string; options?: StoryOption[]; generated_by?: GeneratedBy };
          if (mounted && created.text) {
            setMessages([assistantMessage(created.text, created.generated_by)]);
          }
          if (mounted && created.options) {
            setOptions(created.options);
          }
        }
        await refreshSession();
      } catch (err) {
        if (mounted) {
          setError(err instanceof Error ? err.message : t('game.loadSessionError'));
        }
      }
    }

    void init();

    return () => {
      mounted = false;
      clearPolling();
    };
  }, [sessionId, devMode]);

  useEffect(() => {
    setSelectedPerfOptions([]);
  }, [currentSceneId, round, options]);

  async function submitTurn(input: string, displayText?: string) {
    if (submitting || settling || status !== 'active') {
      return;
    }
    setError(null);
    setSubmitting(true);
    setMessages((prev) => [...prev, { id: uid(), role: 'user', content: displayText || input }]);

    try {
      const res = await sendTurn(sessionId, input);
      setMessages((prev) => [...prev, assistantMessage(res.text, res.generated_by)]);
      setOptions(res.options || []);
      setRound(res.round);
      if (res.game_ended) {
        setStatus('ended');
        setEnding(res.ending || null);
        setSettling(false);
        clearPolling();
        return;
      }
      if (res.scene_ended) {
        startPolling(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t('game.submitError');
      setError(message);
      if (message.includes('settlement in progress')) {
        startPolling(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const inputDisabled = submitting || settling || status !== 'active';
  const isPerfReviewPickTwo = currentSceneId === 'perf_review_cycle' && round === 0;
  const isPerfReviewFramingPick = currentSceneId === 'perf_review_cycle' && round === 1;
  const perfSubmitDisabled = inputDisabled || selectedPerfOptions.length !== 2;

  function togglePerfOption(optionId: string) {
    if (inputDisabled) {
      return;
    }
    setSelectedPerfOptions((prev) => {
      if (prev.includes(optionId)) {
        return prev.filter((id) => id !== optionId);
      }
      if (prev.length >= 2) {
        return [...prev.slice(1), optionId];
      }
      return [...prev, optionId];
    });
  }

  function togglePerfFramingOption(optionId: string) {
    if (inputDisabled) {
      return;
    }
    const group = optionId.charAt(0);
    setSelectedPerfOptions((prev) => {
      const withoutGroup = prev.filter((id) => id.charAt(0) !== group);
      if (prev.includes(optionId)) {
        return withoutGroup;
      }
      return [...withoutGroup, optionId];
    });
  }

  async function submitPerfSelection() {
    if (selectedPerfOptions.length !== 2) {
      return;
    }
    const ordered = [...selectedPerfOptions].sort((left, right) => left.localeCompare(right, 'en'));
    await submitTurn(ordered.join(' '), `${t('game.perfSelection')}：${ordered.join(' + ')}`);
  }

  async function submitPerfFramingSelection() {
    if (selectedPerfOptions.length !== 2) {
      return;
    }
    const ordered = [...selectedPerfOptions].sort((left, right) => left.localeCompare(right, 'en'));
    await submitTurn(ordered.join(' '), `${t('game.perfFraming')}：${ordered.join(' + ')}`);
  }

  const inputBarEmptySubmit = isPerfReviewPickTwo
    ? submitPerfSelection
    : isPerfReviewFramingPick
      ? submitPerfFramingSelection
      : undefined;

  return (
    <main className="mx-auto flex h-screen w-full max-w-7xl flex-col overflow-hidden px-4 py-4 md:px-6 md:py-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-black">Hooli Survival</h1>
          <p className="mono text-xs text-black/60">
            {t('game.session')} {sessionId.slice(0, 8)} • {t('game.round')} {round}/{maxRounds || '?'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={restartGame}
            className="mono rounded-md border border-black/60 px-3 py-1 text-xs text-black transition hover:bg-black hover:text-white"
          >
            {t('game.restart')}
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 grid gap-4 md:grid-cols-[minmax(0,1fr)_290px]">
        <section className="flex min-h-0 min-w-0 flex-col">
          <ChatWindow messages={messages} assistantTyping={submitting && !settling && status === 'active'} showGeneratedBy={devMode} />
          {submitting && isPerfReviewFramingPick ? (
            <SceneTransition message={t('transition.perf')} />
          ) : null}
          {settling ? (
            <SceneTransition message={t('transition.nextScene')} />
          ) : null}
          {status === 'ended' ? (
            <EndingView ending={ending} onRestart={restartGame} />
          ) : null}
          {!inputDisabled ? (
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {isPerfReviewPickTwo ? (
                <>
                  {options.map((option) => {
                    const selected = selectedPerfOptions.includes(option.id);
                    return (
                      <button
                        key={option.id}
                        disabled={inputDisabled}
                        onClick={() => togglePerfOption(option.id)}
                        className={[
                          'min-w-0 break-words rounded-xl border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                          selected
                            ? 'border-black bg-black text-white'
                            : 'border-black/40 bg-white text-black hover:bg-black hover:text-white',
                        ].join(' ')}
                      >
                        <span className={`mono mr-2 text-xs ${selected ? 'text-white/70' : 'text-black/60'}`}>
                          {option.id}.
                        </span>
                        {option.text}
                      </button>
                    );
                  })}
                  <button
                    disabled={perfSubmitDisabled}
                    onClick={() => void submitPerfSelection()}
                    className="rounded-xl border border-black bg-black px-3 py-2 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
                  >
                    {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                  </button>
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className="rounded-xl border border-dashed border-black/40 bg-white px-3 py-2 text-left text-sm text-black/75 transition hover:border-black disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
                  >
                    {t('game.chooseInput')}
                  </button>
                </>
              ) : isPerfReviewFramingPick ? (
                <>
                  {options.map((option) => {
                    const selected = selectedPerfOptions.includes(option.id);
                    return (
                      <button
                        key={option.id}
                        disabled={inputDisabled}
                        onClick={() => togglePerfFramingOption(option.id)}
                        className={[
                          'min-w-0 break-words rounded-xl border px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                          selected
                            ? 'border-black bg-black text-white'
                            : 'border-black/40 bg-white text-black hover:bg-black hover:text-white',
                        ].join(' ')}
                      >
                        <span className={`mono mr-2 text-xs ${selected ? 'text-white/70' : 'text-black/60'}`}>
                          {option.id}
                        </span>
                        {option.text}
                      </button>
                    );
                  })}
                  <button
                    disabled={perfSubmitDisabled}
                    onClick={() => void submitPerfFramingSelection()}
                    className="rounded-xl border border-black bg-black px-3 py-2 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
                  >
                    {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                  </button>
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className="rounded-xl border border-dashed border-black/40 bg-white px-3 py-2 text-left text-sm text-black/75 transition hover:border-black disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
                  >
                    {t('game.chooseInput')}
                  </button>
                </>
              ) : (
                <>
                  {options.map((option) => (
                    <button
                      key={option.id}
                      disabled={inputDisabled}
                      onClick={() => void submitTurn(option.id, option.text)}
                      className="min-w-0 break-words rounded-xl border border-black/40 bg-white px-3 py-2 text-left text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40"
                    >
                      <span className="mono mr-2 text-xs text-black/60">{option.id}.</span>
                      {option.text}
                    </button>
                  ))}
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className={`min-w-0 break-words rounded-xl border border-dashed border-black/40 bg-white px-3 py-2 text-left text-sm text-black/75 transition hover:border-black disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35 ${options.length > 0 ? '' : 'md:col-span-2'}`}
                  >
                    {options.length > 0 ? t('game.chooseInput') : t('game.freeInput')}
                  </button>
                </>
              )}
            </div>
          ) : null}
          {status === 'active' ? (
            <>
              <InputBar
                disabled={inputDisabled}
                onSubmit={submitTurn}
                onEmptySubmit={inputBarEmptySubmit}
                inputRef={inputRef}
                placeholder={settling ? t('game.settlingPlaceholder') : t('game.inputPlaceholder')}
              />
              <p className="mt-2 text-xs text-black/55 mono">{t('game.freeInputHint')}</p>
            </>
          ) : null}
          {error ? <p className="mt-3 text-sm text-black/70">{error}</p> : null}
        </section>

        <StatPanel characters={characters} state={state} latestEval={latestEval} />
      </div>
    </main>
  );
}
