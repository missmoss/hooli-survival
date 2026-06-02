'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';

import ChatWindow, { ChatMessage } from '@/components/ChatWindow';
import EndingView from '@/components/EndingView';
import InputBar from '@/components/InputBar';
import SceneSummaryCard from '@/components/SceneSummaryCard';
import SceneTransition from '@/components/SceneTransition';
import StatPanel from '@/components/StatPanel';
import {
  CharacterCard,
  EndingPayload,
  GeneratedBy,
  LatestEval,
  NextSceneResponse,
  StoryOption,
  getNextScene,
  getSession,
  sendTurn,
} from '@/lib/api';
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
  const editorialTheme = searchParams.get('theme') === 'editorial';

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [options, setOptions] = useState<StoryOption[]>([]);
  const [currentSceneId, setCurrentSceneId] = useState('');
  const [characters, setCharacters] = useState<{
    manager: CharacterCard;
    buddy: CharacterCard;
    team_members: CharacterCard[];
  } | null>(null);
  const [state, setState] = useState<Record<string, number> | null>(null);
  const [latestEval, setLatestEval] = useState<LatestEval | null>(null);
  const [round, setRound] = useState(0);
  const [maxRounds, setMaxRounds] = useState(0);
  const [status, setStatus] = useState('active');
  const [ending, setEnding] = useState<EndingPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [settling, setSettling] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedPerfOptions, setSelectedPerfOptions] = useState<string[]>([]);
  const [summaryEval, setSummaryEval] = useState<LatestEval | null>(null);
  const [pendingScene, setPendingScene] = useState<Extract<NextSceneResponse, { ready: true }> | null>(null);
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);
  const [mobileActionOpen, setMobileActionOpen] = useState(false);
  const [mobileComposerOpen, setMobileComposerOpen] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollLockRef = useRef(false);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  function sceneSummaryEligible(sceneId: string): boolean {
    return !['perf_review_cycle', 'pip_cycle', 'promo_result', 'reorg_cycle'].includes(sceneId);
  }

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
        const shouldPauseForSummary = sceneSummaryEligible(currentSceneId);
        if (shouldPauseForSummary) {
          setPendingScene(next);
          await refreshSession();
          return true;
        }
        setMessages((prev) => [...prev, { id: uid(), role: 'divider', content: t('game.newScene') }, assistantMessage(next.text, next.generated_by)]);
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

  function revealPendingScene() {
    if (!pendingScene) {
      return;
    }
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: 'divider', content: t('game.newScene') },
      assistantMessage(pendingScene.text, pendingScene.generated_by),
    ]);
    setCurrentSceneId(pendingScene.scene_id);
    setOptions(pendingScene.options || []);
    setPendingScene(null);
    setSummaryEval(null);
  }

  function restartGame() {
    sessionStorage.removeItem(`hooli:session:${sessionId}`);
    router.push('/');
  }

  function closeMobileSurfaces() {
    setMobilePanelOpen(false);
    setMobileActionOpen(false);
    setMobileComposerOpen(false);
  }

  function openMobileActions() {
    setMobilePanelOpen(false);
    setMobileActionOpen(true);
    setMobileComposerOpen(options.length === 0);
  }

  function openMobileComposer() {
    setMobileComposerOpen(true);
  }

  function backToMobileOptions() {
    setMobileComposerOpen(false);
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

  useEffect(() => {
    closeMobileSurfaces();
  }, [currentSceneId, round]);

  useEffect(() => {
    if (!pendingScene || !latestEval) {
      return;
    }
    if (latestEval.scene_id !== currentSceneId) {
      setSummaryEval(latestEval);
    }
  }, [pendingScene, latestEval, currentSceneId]);

  useEffect(() => {
    if (mobileComposerOpen) {
      inputRef.current?.focus();
    }
  }, [mobileComposerOpen]);

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

  const summaryVisible = Boolean(summaryEval && pendingScene);
  const waitingForSummary = Boolean(pendingScene && !summaryEval);
  const inputDisabled = submitting || settling || status !== 'active' || Boolean(pendingScene);
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

  async function submitTurnFromMobile(input: string, displayText?: string) {
    closeMobileSurfaces();
    await submitTurn(input, displayText);
  }

  async function submitPerfSelectionFromMobile() {
    closeMobileSurfaces();
    await submitPerfSelection();
  }

  async function submitPerfFramingSelectionFromMobile() {
    closeMobileSurfaces();
    await submitPerfFramingSelection();
  }

  const inputBarEmptySubmit = isPerfReviewPickTwo
    ? submitPerfSelection
    : isPerfReviewFramingPick
      ? submitPerfFramingSelection
      : undefined;
  const mobileInputBarEmptySubmit = isPerfReviewPickTwo
    ? submitPerfSelectionFromMobile
    : isPerfReviewFramingPick
      ? submitPerfFramingSelectionFromMobile
      : undefined;
  const endingMode = status === 'ended';
  const theme = editorialTheme ? 'editorial' : 'default';

  return (
    <main
      className={[
        `mx-auto flex w-full ${endingMode ? 'max-w-5xl' : 'max-w-7xl'} flex-col px-3 py-3 sm:px-4 sm:py-4 md:px-6 md:py-6`,
        endingMode
          ? 'min-h-[100dvh] overflow-y-auto'
          : 'h-[100dvh] min-h-[100dvh] overflow-hidden',
        editorialTheme ? 'text-slate-900' : '',
      ].join(' ')}
    >
      <div
        className={[
          'mb-3 px-1 py-1 sm:mb-4',
          editorialTheme
            ? 'border border-transparent bg-transparent shadow-none'
            : '',
        ].join(' ')}
      >
      <div className={['flex flex-wrap items-center justify-between gap-3', editorialTheme ? 'md:grid md:grid-cols-[minmax(0,1fr)_272px] md:items-start' : ''].join(' ')}>
        <div className={editorialTheme ? 'min-w-0 space-y-2' : 'min-w-0'}>
          <h1 className={['text-xl font-semibold', editorialTheme ? 'text-slate-950' : 'text-black'].join(' ')}>Hooli Survival</h1>
          {!endingMode ? (
            editorialTheme ? (
              <div className="flex flex-wrap items-center gap-3 text-[11px]">
                <span className="mono uppercase tracking-[0.14em] text-slate-500">{t('game.session')}</span>
                <span className="mono text-slate-900">{sessionId.slice(0, 8)}</span>
                <span className="h-3.5 w-px bg-slate-300" />
                <span className="mono uppercase tracking-[0.14em] text-slate-500">{t('game.round')}</span>
                <span className="mono text-slate-900">{round}/{maxRounds || '?'}</span>
              </div>
            ) : (
              <p className="mono text-xs text-black/60">
                {t('game.session')} {sessionId.slice(0, 8)} • {t('game.round')} {round}/{maxRounds || '?'}
              </p>
            )
          ) : null}
        </div>
        <div className={['grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-2 sm:flex sm:w-auto', editorialTheme ? 'md:w-full md:justify-self-stretch md:justify-end' : 'md:flex'].join(' ')}>
          {status === 'active' ? (
            <button
              disabled={inputDisabled}
              onClick={() => {
                setMobileActionOpen(false);
                setMobileComposerOpen(false);
                setMobilePanelOpen(true);
              }}
              className={[
                'mono rounded-[0.8rem] px-3 py-1.5 text-[12px] transition disabled:cursor-not-allowed md:hidden',
                editorialTheme
                  ? 'border border-slate-300 bg-white text-slate-800 hover:border-slate-500 disabled:border-slate-200 disabled:text-slate-300'
                  : 'border border-black/40 text-black/70 hover:border-black hover:bg-white disabled:border-black/20 disabled:text-black/35',
              ].join(' ')}
            >
              {t('mobile.teamState')} ▾
            </button>
          ) : null}
          <button
            onClick={restartGame}
            className={[
              'mono rounded-[0.8rem] px-3 py-1.5 text-[12px] transition',
              editorialTheme
                ? 'border border-slate-300 bg-white text-slate-900 hover:border-slate-500 hover:bg-slate-50'
                : 'border border-black/60 text-black hover:bg-black hover:text-white',
            ].join(' ')}
          >
            {t('game.restart')}
          </button>
        </div>
      </div>
      </div>

      <div
        className={[
          'min-h-0 flex-1 grid gap-3 md:gap-4',
          endingMode ? 'pb-6 md:grid-cols-1' : 'pb-20 md:pb-0 md:grid-cols-[minmax(0,1fr)_272px]',
        ].join(' ')}
      >
        <section
          className={[
            `flex min-h-0 min-w-0 flex-col ${endingMode ? 'mx-auto w-full max-w-5xl' : ''}`,
            editorialTheme && !endingMode
              ? 'rounded-[0.62rem] border border-slate-300/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,251,0.95))] p-3 shadow-[0_12px_24px_rgba(15,23,42,0.04)] sm:p-3.5'
              : '',
          ].join(' ')}
        >
          <div className={endingMode ? 'hidden' : 'flex min-h-0 flex-1 flex-col'}>
            <ChatWindow messages={messages} assistantTyping={submitting && !settling && status === 'active'} showGeneratedBy={devMode} theme={theme} />
            {submitting && isPerfReviewFramingPick ? (
              <SceneTransition message={t('transition.perf')} theme={theme} />
            ) : null}
            {settling ? (
              <SceneTransition message={t('transition.nextScene')} theme={theme} />
            ) : null}
            {waitingForSummary ? (
              <SceneTransition message={t('transition.nextScene')} theme={theme} />
            ) : null}
            {summaryVisible && summaryEval ? (
              <SceneSummaryCard evaluation={summaryEval} onContinue={revealPendingScene} theme={theme} />
            ) : null}
          </div>
          {status === 'ended' ? (
            <EndingView ending={ending} stats={state} onRestart={restartGame} theme={theme} />
          ) : null}
          {!inputDisabled ? (
            <div className={['mt-3 hidden gap-2 sm:mt-4 md:grid', editorialTheme ? 'md:grid-cols-1' : 'md:grid-cols-2'].join(' ')}>
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
                          'min-w-0 break-words rounded-[0.85rem] border px-3.5 py-2 text-left text-[12px] leading-[1.45] transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                          editorialTheme
                            ? selected
                              ? 'rounded-none border-x-0 border-t-0 border-b border-blue-700 bg-transparent px-0 text-blue-700 shadow-none'
                              : 'rounded-none border-x-0 border-t-0 border-b border-slate-200 bg-transparent px-0 text-slate-800 shadow-none hover:border-slate-400 hover:text-slate-950'
                            : selected
                              ? 'border-black bg-black text-white'
                              : 'border-black/40 bg-white text-black hover:bg-black hover:text-white',
                        ].join(' ')}
                      >
                        <span
                          className={[
                            'mono mr-2 text-xs',
                            editorialTheme ? (selected ? 'text-blue-600' : 'text-slate-400') : selected ? 'text-white/70' : 'text-black/60',
                          ].join(' ')}
                        >
                          {option.id}.
                        </span>
                        {option.text}
                      </button>
                    );
                  })}
                  <button
                    disabled={perfSubmitDisabled}
                    onClick={() => void submitPerfSelection()}
                    className={[
                      'rounded-[0.85rem] px-3.5 py-2 text-[12px] transition disabled:cursor-not-allowed',
                      editorialTheme
                        ? 'rounded-[0.58rem] border border-blue-700 bg-blue-700 text-white hover:bg-blue-800 disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400'
                        : 'border border-black bg-black text-white hover:bg-white hover:text-black disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
                    ].join(' ')}
                  >
                    {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                  </button>
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className={[
                      'rounded-[0.85rem] border px-3.5 py-2 text-left text-[12px] transition disabled:cursor-not-allowed',
                      editorialTheme
                        ? 'rounded-none border-0 bg-transparent px-0 text-slate-500 hover:text-slate-800 disabled:text-slate-300'
                        : 'border-dashed border-black/40 bg-white text-black/75 hover:border-black disabled:border-black/20 disabled:text-black/35',
                    ].join(' ')}
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
                          'min-w-0 break-words rounded-[0.85rem] border px-3.5 py-2 text-left text-[12px] leading-[1.45] transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                          editorialTheme
                            ? selected
                              ? 'rounded-none border-x-0 border-t-0 border-b border-blue-700 bg-transparent px-0 text-blue-700 shadow-none'
                              : 'rounded-none border-x-0 border-t-0 border-b border-slate-200 bg-transparent px-0 text-slate-800 shadow-none hover:border-slate-400 hover:text-slate-950'
                            : selected
                              ? 'border-black bg-black text-white'
                              : 'border-black/40 bg-white text-black hover:bg-black hover:text-white',
                        ].join(' ')}
                      >
                        <span
                          className={[
                            'mono mr-2 text-xs',
                            editorialTheme ? (selected ? 'text-blue-600' : 'text-slate-400') : selected ? 'text-white/70' : 'text-black/60',
                          ].join(' ')}
                        >
                          {option.id}
                        </span>
                        {option.text}
                      </button>
                    );
                  })}
                  <button
                    disabled={perfSubmitDisabled}
                    onClick={() => void submitPerfFramingSelection()}
                    className={[
                      'rounded-[0.85rem] px-3.5 py-2 text-[12px] transition disabled:cursor-not-allowed',
                      editorialTheme
                        ? 'rounded-[0.58rem] border border-blue-700 bg-blue-700 text-white hover:bg-blue-800 disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400'
                        : 'border border-black bg-black text-white hover:bg-white hover:text-black disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
                    ].join(' ')}
                  >
                    {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                  </button>
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className={[
                      'rounded-[0.85rem] border px-3.5 py-2 text-left text-[12px] transition disabled:cursor-not-allowed',
                      editorialTheme
                        ? 'rounded-none border-0 bg-transparent px-0 text-slate-500 hover:text-slate-800 disabled:text-slate-300'
                        : 'border-dashed border-black/40 bg-white text-black/75 hover:border-black disabled:border-black/20 disabled:text-black/35',
                    ].join(' ')}
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
                      className={[
                        'min-w-0 break-words rounded-[0.85rem] border px-3.5 py-2 text-left text-[12px] leading-[1.45] transition disabled:cursor-not-allowed',
                        editorialTheme
                          ? 'rounded-none border-x-0 border-t-0 border-b border-slate-200 bg-transparent px-0 text-slate-800 shadow-none hover:border-slate-400 hover:text-slate-950 disabled:border-slate-100 disabled:text-slate-400'
                          : 'border-black/40 bg-white text-black hover:bg-black hover:text-white disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                      ].join(' ')}
                    >
                      <span className={['mono mr-2 text-xs', editorialTheme ? 'text-slate-400' : 'text-black/60'].join(' ')}>{option.id}.</span>
                      {option.text}
                    </button>
                  ))}
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className={[
                      `min-w-0 break-words rounded-[0.85rem] border px-3.5 py-2 text-left text-[12px] transition disabled:cursor-not-allowed ${options.length > 0 ? '' : 'md:col-span-2'}`,
                      editorialTheme
                        ? 'rounded-none border-0 bg-transparent px-0 text-slate-500 hover:text-slate-800 disabled:text-slate-300'
                        : 'border-dashed border-black/40 bg-white text-black/75 hover:border-black disabled:border-black/20 disabled:text-black/35',
                    ].join(' ')}
                  >
                    {options.length > 0 ? t('game.chooseInput') : t('game.freeInput')}
                  </button>
                </>
              )}
            </div>
          ) : null}
          {status === 'active' ? (
            <>
              <div className={editorialTheme ? 'hidden md:block rounded-[0.58rem] bg-transparent px-1 pb-0' : 'hidden md:block'}>
                <InputBar
                  disabled={inputDisabled}
                  onSubmit={submitTurn}
                  onEmptySubmit={inputBarEmptySubmit}
                  inputRef={inputRef}
                  placeholder={settling ? t('game.settlingPlaceholder') : t('game.inputPlaceholder')}
                  theme={theme}
                />
                <p className={['mt-2 text-xs mono', editorialTheme ? 'text-slate-500' : 'text-black/55'].join(' ')}>{t('game.freeInputHint')}</p>
              </div>
            </>
          ) : null}
          {error ? <p className={['mt-3 text-sm', editorialTheme ? 'text-rose-700' : 'text-black/70'].join(' ')}>{error}</p> : null}
        </section>

        {!endingMode ? <StatPanel characters={characters} state={state} latestEval={latestEval} className="hidden md:block" theme={theme} /> : null}
      </div>

      {status === 'active' ? (
        <div
          className={[
            'fixed inset-x-0 bottom-0 z-30 px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3 backdrop-blur-sm md:hidden',
            editorialTheme
              ? 'border-t border-slate-200 bg-[rgba(248,250,252,0.96)]'
              : 'border-t border-black/15 bg-[rgba(246,246,246,0.96)]',
          ].join(' ')}
        >
          <div className="mx-auto max-w-7xl">
            <button
              disabled={inputDisabled}
              onClick={openMobileActions}
              className={[
                'mono w-full rounded-xl px-3 py-3 text-sm transition disabled:cursor-not-allowed',
                editorialTheme
                  ? 'border border-blue-600 bg-blue-600 text-white hover:bg-blue-700 disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400'
                  : 'border border-black bg-black text-white hover:bg-white hover:text-black disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40',
              ].join(' ')}
            >
              {t('mobile.chooseAction')}
            </button>
          </div>
        </div>
      ) : null}

      {mobilePanelOpen ? (
        <div className="fixed inset-0 z-40 md:hidden" aria-modal="true" role="dialog">
          <button
            aria-label={t('panel.close')}
            onClick={closeMobileSurfaces}
            className="absolute inset-0 bg-black/35 backdrop-blur-[2px]"
          />
          <div
            className={[
              'absolute inset-x-0 bottom-0 flex max-h-[78dvh] flex-col rounded-t-[1.75rem] px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3',
              editorialTheme
                ? 'border border-slate-200 bg-slate-50 shadow-[0_-24px_60px_rgba(15,23,42,0.16)]'
                : 'border border-black/20 bg-[#f6f6f6] shadow-frame',
            ].join(' ')}
          >
            <div className="mb-2 flex justify-end">
              <button
                onClick={closeMobileSurfaces}
                className={[
                  'mono rounded-md bg-white/90 px-3 py-1 text-xs',
                  editorialTheme ? 'border border-slate-300 text-slate-700' : 'border border-black/60 text-black shadow-frame',
                ].join(' ')}
              >
                {t('panel.close')}
              </button>
            </div>
            <StatPanel characters={characters} state={state} latestEval={latestEval} className="flex-1 bg-white/95" theme={theme} />
          </div>
        </div>
      ) : null}

      {mobileActionOpen ? (
        <div className="fixed inset-0 z-40 md:hidden" aria-modal="true" role="dialog">
          <button
            aria-label={t('panel.close')}
            onClick={closeMobileSurfaces}
            className="absolute inset-0 bg-black/35 backdrop-blur-[2px]"
          />
          <div
            className={[
              'absolute inset-x-0 bottom-0 flex max-h-[82dvh] flex-col rounded-t-[1.75rem] px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3',
              editorialTheme
                ? 'border border-slate-200 bg-slate-50 shadow-[0_-24px_60px_rgba(15,23,42,0.16)]'
                : 'border border-black/20 bg-[#f6f6f6] shadow-frame',
            ].join(' ')}
          >
            <div className="mb-2 flex justify-end">
              <button
                onClick={closeMobileSurfaces}
                className={[
                  'mono rounded-md bg-white/90 px-3 py-1 text-xs',
                  editorialTheme ? 'border border-slate-300 text-slate-700' : 'border border-black/60 text-black shadow-frame',
                ].join(' ')}
              >
                {t('panel.close')}
              </button>
            </div>
            <div className="min-h-0 overflow-y-auto">
              {mobileComposerOpen ? (
                <div>
                  {options.length > 0 ? (
                    <button
                      onClick={backToMobileOptions}
                      className={[
                        'mono mb-2 rounded-xl border px-3 py-3 text-left text-sm transition',
                        editorialTheme ? 'rounded-none border-0 bg-transparent px-0 text-slate-500 hover:text-slate-800' : 'border-dashed border-black/40 bg-white text-black/75 hover:border-black',
                      ].join(' ')}
                    >
                      {t('mobile.backToOptions')}
                    </button>
                  ) : null}
                  <InputBar
                    disabled={inputDisabled}
                    onSubmit={submitTurnFromMobile}
                    onEmptySubmit={mobileInputBarEmptySubmit}
                    inputRef={inputRef}
                    placeholder={settling ? t('game.settlingPlaceholder') : t('game.inputPlaceholder')}
                    theme={theme}
                  />
                  <p className={['mt-2 text-xs mono', editorialTheme ? 'text-slate-500' : 'text-black/55'].join(' ')}>{t('game.freeInputHint')}</p>
                </div>
              ) : (
                <div className="grid gap-2">
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
                              'min-w-0 break-words rounded-xl border px-3 py-3 text-left text-sm transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                              editorialTheme
                                ? selected
                                  ? 'rounded-none border-x-0 border-t-0 border-b border-blue-700 bg-transparent px-0 text-blue-700'
                                  : 'rounded-none border-x-0 border-t-0 border-b border-slate-200 bg-transparent px-0 text-slate-800 hover:border-slate-400 hover:text-slate-950'
                                : selected
                                  ? 'border-black bg-black text-white'
                                  : 'border-black/40 bg-white text-black hover:bg-black hover:text-white',
                            ].join(' ')}
                          >
                            <span className={`mono mr-2 text-xs ${editorialTheme ? (selected ? 'text-blue-600' : 'text-slate-400') : selected ? 'text-white/70' : 'text-black/60'}`}>
                              {option.id}.
                            </span>
                            {option.text}
                          </button>
                        );
                      })}
                      <button
                        disabled={perfSubmitDisabled}
                        onClick={() => void submitPerfSelectionFromMobile()}
                        className={editorialTheme ? 'rounded-[0.58rem] border border-blue-700 bg-blue-700 px-3 py-2 text-sm text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400' : 'rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40'}
                      >
                        {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                      </button>
                      <button
                        disabled={inputDisabled}
                        onClick={openMobileComposer}
                        className={editorialTheme ? 'rounded-none border-0 bg-transparent px-0 py-2 text-left text-sm text-slate-500 transition hover:text-slate-800 disabled:cursor-not-allowed disabled:text-slate-300' : 'rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35'}
                      >
                        {t('mobile.writeCustom')}
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
                              'min-w-0 break-words rounded-xl border px-3 py-3 text-left text-sm transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
                              editorialTheme
                                ? selected
                                  ? 'rounded-none border-x-0 border-t-0 border-b border-blue-700 bg-transparent px-0 text-blue-700'
                                  : 'rounded-none border-x-0 border-t-0 border-b border-slate-200 bg-transparent px-0 text-slate-800 hover:border-slate-400 hover:text-slate-950'
                                : selected
                                  ? 'border-black bg-black text-white'
                                  : 'border-black/40 bg-white text-black hover:bg-black hover:text-white',
                            ].join(' ')}
                          >
                            <span className={`mono mr-2 text-xs ${editorialTheme ? (selected ? 'text-blue-600' : 'text-slate-400') : selected ? 'text-white/70' : 'text-black/60'}`}>
                              {option.id}
                            </span>
                            {option.text}
                          </button>
                        );
                      })}
                      <button
                        disabled={perfSubmitDisabled}
                        onClick={() => void submitPerfFramingSelectionFromMobile()}
                        className={editorialTheme ? 'rounded-[0.58rem] border border-blue-700 bg-blue-700 px-3 py-2 text-sm text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-200 disabled:text-slate-400' : 'rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40'}
                      >
                        {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                      </button>
                      <button
                        disabled={inputDisabled}
                        onClick={openMobileComposer}
                        className={editorialTheme ? 'rounded-none border-0 bg-transparent px-0 py-2 text-left text-sm text-slate-500 transition hover:text-slate-800 disabled:cursor-not-allowed disabled:text-slate-300' : 'rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35'}
                      >
                        {t('mobile.writeCustom')}
                      </button>
                    </>
                  ) : (
                    <>
                      {options.map((option) => (
                        <button
                          key={option.id}
                          disabled={inputDisabled}
                          onClick={() => void submitTurnFromMobile(option.id, option.text)}
                          className={editorialTheme ? 'min-w-0 break-words rounded-none border-x-0 border-t-0 border-b border-slate-200 bg-transparent px-0 py-3 text-left text-sm text-slate-800 transition hover:border-slate-400 hover:text-slate-950 disabled:cursor-not-allowed disabled:border-slate-100 disabled:text-slate-400' : 'min-w-0 break-words rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40'}
                        >
                          <span className={editorialTheme ? 'mono mr-2 text-xs text-slate-400' : 'mono mr-2 text-xs text-black/60'}>{option.id}.</span>
                          {option.text}
                        </button>
                      ))}
                      <button
                        disabled={inputDisabled}
                        onClick={openMobileComposer}
                        className={editorialTheme ? 'rounded-none border-0 bg-transparent px-0 py-2 text-left text-sm text-slate-500 transition hover:text-slate-800 disabled:cursor-not-allowed disabled:text-slate-300' : 'rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35'}
                      >
                        {options.length > 0 ? t('mobile.writeCustom') : t('game.freeInput')}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
