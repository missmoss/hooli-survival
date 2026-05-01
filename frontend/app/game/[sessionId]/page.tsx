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
  const portalEntry = searchParams.get('portal') === 'true';
  const portalRef = (searchParams.get('ref') || '').trim();

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

  function readStoredPlayerName(): string {
    if (typeof window === 'undefined') {
      return '';
    }
    try {
      const raw = sessionStorage.getItem(`hooli:session:${sessionId}`);
      if (!raw) {
        return '';
      }
      const saved = JSON.parse(raw) as { player_name?: string };
      return (saved.player_name || '').trim();
    } catch {
      return '';
    }
  }

  function buildOutgoingPortalParams() {
    const params = new URLSearchParams();
    const playerName = readStoredPlayerName() || (searchParams.get('username') || '').trim();
    if (playerName) {
      params.set('username', playerName);
    }
    if (typeof window !== 'undefined') {
      params.set('ref', window.location.origin);
    }
    return params;
  }

  function openGameJamPortal() {
    const portalUrl = new URL('https://vibejam.cc/portal/2026');
    if (typeof window !== 'undefined') {
      buildOutgoingPortalParams().forEach((value, key) => {
        portalUrl.searchParams.set(key, value);
      });
      window.location.assign(portalUrl.toString());
    }
  }

  function normalizePortalRef(target: string): string | null {
    const trimmed = target.trim();
    if (!trimmed) {
      return null;
    }
    try {
      return new URL(trimmed).toString();
    } catch {
      try {
        return new URL(`https://${trimmed}`).toString();
      } catch {
        return null;
      }
    }
  }

  function openReturnPortal() {
    const target = normalizePortalRef(portalRef);
    if (!target) {
      return;
    }
    const url = new URL(target);
    const params = new URLSearchParams(searchParams.toString());
    params.set('portal', 'true');
    buildOutgoingPortalParams().forEach((value, key) => {
      params.set(key, value);
    });
    url.search = params.toString();
    if (typeof window !== 'undefined') {
      window.location.assign(url.toString());
    }
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

  return (
    <main
      className={[
        'mx-auto flex w-full max-w-7xl flex-col px-3 py-3 sm:px-4 sm:py-4 md:px-6 md:py-6',
        endingMode
          ? 'min-h-[100dvh] overflow-y-auto'
          : 'h-[100dvh] min-h-[100dvh] overflow-hidden',
      ].join(' ')}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 sm:mb-4">
        <div>
          <h1 className="text-xl font-semibold text-black">Hooli Survival</h1>
          {!endingMode ? (
            <p className="mono text-xs text-black/60">
              {t('game.session')} {sessionId.slice(0, 8)} • {t('game.round')} {round}/{maxRounds || '?'}
            </p>
          ) : null}
        </div>
        <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-2 sm:flex sm:w-auto md:flex">
          {status === 'active' ? (
            <button
              disabled={inputDisabled}
              onClick={() => {
                setMobileActionOpen(false);
                setMobileComposerOpen(false);
                setMobilePanelOpen(true);
              }}
              className="mono rounded-md border border-black/40 px-3 py-1.5 text-xs text-black/70 transition hover:border-black hover:bg-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35 md:hidden"
            >
              {t('mobile.teamState')} ▾
            </button>
          ) : null}
          <div className="hidden items-center gap-2 md:flex">
            <button
              onClick={openGameJamPortal}
              className="mono rounded-full border border-black bg-black px-3 py-1.5 text-xs text-white shadow-frame transition hover:bg-white hover:text-black"
            >
              {t('game.portal')}
            </button>
            {portalEntry && portalRef ? (
              <button
                onClick={openReturnPortal}
                className="mono rounded-full border border-black/60 bg-white/85 px-3 py-1.5 text-xs text-black shadow-frame transition hover:bg-black hover:text-white"
              >
                {t('game.returnPortal')}
              </button>
            ) : null}
          </div>
          <button
            onClick={restartGame}
            className="mono rounded-md border border-black/60 px-3 py-1.5 text-xs text-black transition hover:bg-black hover:text-white"
          >
            {t('game.restart')}
          </button>
        </div>
      </div>

      <div
        className={[
          'min-h-0 flex-1 grid gap-3 md:gap-4',
          endingMode ? 'pb-6 md:grid-cols-1' : 'pb-20 md:pb-0 md:grid-cols-[minmax(0,1fr)_290px]',
        ].join(' ')}
      >
        <section className={`flex min-h-0 min-w-0 flex-col ${endingMode ? 'mx-auto w-full max-w-5xl' : ''}`}>
          <div className={endingMode ? 'hidden' : 'flex min-h-0 flex-1 flex-col'}>
            <ChatWindow messages={messages} assistantTyping={submitting && !settling && status === 'active'} showGeneratedBy={devMode} />
            {submitting && isPerfReviewFramingPick ? (
              <SceneTransition message={t('transition.perf')} />
            ) : null}
            {settling ? (
              <SceneTransition message={t('transition.nextScene')} />
            ) : null}
            {waitingForSummary ? (
              <SceneTransition message={t('transition.nextScene')} />
            ) : null}
            {summaryVisible && summaryEval ? (
              <SceneSummaryCard evaluation={summaryEval} onContinue={revealPendingScene} />
            ) : null}
          </div>
          {status === 'ended' ? (
            <EndingView ending={ending} stats={state} onRestart={restartGame} />
          ) : null}
          {!inputDisabled ? (
            <div className="mt-3 hidden gap-2 sm:mt-4 md:grid md:grid-cols-2">
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
                    className="rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
                  >
                    {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                  </button>
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className="rounded-xl border border-dashed border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:border-black disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
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
                          'min-w-0 break-words rounded-xl border px-3 py-3 text-left text-sm transition disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40',
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
                    className="rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
                  >
                    {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                  </button>
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className="rounded-xl border border-dashed border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:border-black disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
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
                      className="min-w-0 break-words rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40"
                    >
                      <span className="mono mr-2 text-xs text-black/60">{option.id}.</span>
                      {option.text}
                    </button>
                  ))}
                  <button
                    disabled={inputDisabled}
                    onClick={() => inputRef.current?.focus()}
                    className={`min-w-0 break-words rounded-xl border border-dashed border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:border-black disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35 ${options.length > 0 ? '' : 'md:col-span-2'}`}
                  >
                    {options.length > 0 ? t('game.chooseInput') : t('game.freeInput')}
                  </button>
                </>
              )}
            </div>
          ) : null}
          {status === 'active' ? (
            <>
              <div className="hidden md:block">
                <InputBar
                  disabled={inputDisabled}
                  onSubmit={submitTurn}
                  onEmptySubmit={inputBarEmptySubmit}
                  inputRef={inputRef}
                  placeholder={settling ? t('game.settlingPlaceholder') : t('game.inputPlaceholder')}
                />
                <p className="mt-2 text-xs text-black/55 mono">{t('game.freeInputHint')}</p>
              </div>
            </>
          ) : null}
          {error ? <p className="mt-3 text-sm text-black/70">{error}</p> : null}
        </section>

        {!endingMode ? <StatPanel characters={characters} state={state} latestEval={latestEval} className="hidden md:block" /> : null}
      </div>

      {status === 'active' ? (
        <div className="fixed inset-x-0 bottom-0 z-30 border-t border-black/15 bg-[rgba(246,246,246,0.96)] px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3 backdrop-blur-sm md:hidden">
          <div className="mx-auto max-w-7xl">
            <button
              disabled={inputDisabled}
              onClick={openMobileActions}
              className="mono w-full rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
            >
              {t('mobile.chooseAction')}
            </button>
          </div>
        </div>
      ) : null}

      <div className="fixed right-3 top-3 z-30 flex flex-col items-end gap-2 md:hidden">
        <button
          onClick={openGameJamPortal}
          className="mono rounded-full border border-black bg-black px-3 py-1.5 text-[11px] text-white shadow-frame transition hover:bg-white hover:text-black"
        >
          {t('game.portal')}
        </button>
        {portalEntry && portalRef ? (
          <button
            onClick={openReturnPortal}
            className="mono rounded-full border border-black/60 bg-white/90 px-3 py-1.5 text-[11px] text-black shadow-frame transition hover:bg-black hover:text-white"
          >
            {t('game.returnPortal')}
          </button>
        ) : null}
      </div>

      {mobilePanelOpen ? (
        <div className="fixed inset-0 z-40 md:hidden" aria-modal="true" role="dialog">
          <button
            aria-label={t('panel.close')}
            onClick={closeMobileSurfaces}
            className="absolute inset-0 bg-black/35 backdrop-blur-[2px]"
          />
          <div className="absolute inset-x-0 bottom-0 flex max-h-[78dvh] flex-col rounded-t-[1.75rem] border border-black/20 bg-[#f6f6f6] px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3 shadow-frame">
            <div className="mb-2 flex justify-end">
              <button
                onClick={closeMobileSurfaces}
                className="mono rounded-md border border-black/60 bg-white/90 px-3 py-1 text-xs text-black shadow-frame"
              >
                {t('panel.close')}
              </button>
            </div>
            <StatPanel characters={characters} state={state} latestEval={latestEval} className="flex-1 bg-white/95" />
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
          <div className="absolute inset-x-0 bottom-0 flex max-h-[82dvh] flex-col rounded-t-[1.75rem] border border-black/20 bg-[#f6f6f6] px-3 pb-[calc(env(safe-area-inset-bottom)+0.75rem)] pt-3 shadow-frame">
            <div className="mb-2 flex justify-end">
              <button
                onClick={closeMobileSurfaces}
                className="mono rounded-md border border-black/60 bg-white/90 px-3 py-1 text-xs text-black shadow-frame"
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
                      className="mono mb-2 rounded-xl border border-dashed border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:border-black"
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
                  />
                  <p className="mt-2 text-xs text-black/55 mono">{t('game.freeInputHint')}</p>
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
                        onClick={() => void submitPerfSelectionFromMobile()}
                        className="rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
                      >
                        {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                      </button>
                      <button
                        disabled={inputDisabled}
                        onClick={openMobileComposer}
                        className="rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
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
                        onClick={() => void submitPerfFramingSelectionFromMobile()}
                        className="rounded-xl border border-black bg-black px-3 py-3 text-sm text-white transition hover:bg-white hover:text-black disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/20 disabled:text-black/40"
                      >
                        {t('game.perfSubmit')} {selectedPerfOptions.length}/2
                      </button>
                      <button
                        disabled={inputDisabled}
                        onClick={openMobileComposer}
                        className="rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
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
                          className="min-w-0 break-words rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:bg-black/5 disabled:text-black/40"
                        >
                          <span className="mono mr-2 text-xs text-black/60">{option.id}.</span>
                          {option.text}
                        </button>
                      ))}
                      <button
                        disabled={inputDisabled}
                        onClick={openMobileComposer}
                        className="rounded-xl border border-black/40 bg-white px-3 py-3 text-left text-sm text-black/75 transition hover:bg-black hover:text-white disabled:cursor-not-allowed disabled:border-black/20 disabled:text-black/35"
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
