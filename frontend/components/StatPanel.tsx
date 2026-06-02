'use client';

import { CharacterCard } from '@/lib/api';
import { useI18n } from '@/lib/i18n';

type Props = {
  characters: {
    manager: CharacterCard;
    buddy: CharacterCard;
    team_members: CharacterCard[];
  } | null;
  state: Record<string, number> | null;
  latestEval?: {
    scene_type: 'project' | 'event';
    scene_id: string;
    rating: string;
    reason: string | null;
    delta: Record<string, number>;
  } | null;
  className?: string;
  theme?: 'default' | 'editorial';
};

const keys = ['tech', 'visibility', 'affinity', 'pip_potential'];

function deltaText(delta: Record<string, number>): string {
  const parts = keys.map((k) => `${((delta[k] ?? 0) as number) >= 0 ? '+' : ''}${delta[k] ?? 0}`);
  return parts.join(' / ');
}

function characterSummary(character: CharacterCard): string {
  return character.display_desc || character.personality_desc || '—';
}

function statLabel(key: string): string {
  const labels: Record<string, string> = {
    tech: 'Tech',
    visibility: 'Visibility',
    affinity: 'Affinity',
    pip_potential: 'PIP Risk',
  };
  return labels[key] || key;
}

function statTone(key: string): string {
  const tones: Record<string, string> = {
    tech: 'bg-blue-500',
    visibility: 'bg-sky-500',
    affinity: 'bg-cyan-500',
    pip_potential: 'bg-slate-700',
  };
  return tones[key] || 'bg-blue-500';
}

function CharacterBlock({
  label,
  character,
  theme,
}: {
  label: string;
  character: CharacterCard;
  theme?: 'default' | 'editorial';
}) {
  const summary = characterSummary(character);
  if (theme === 'editorial') {
    return (
      <div className="grid grid-cols-[56px_minmax(0,1fr)] items-start gap-2.5">
        <div className="mono pt-1 text-[10px] uppercase tracking-[0.14em] text-slate-600">{label}</div>
        <div className="min-w-0 py-1">
          <div className="flex items-baseline gap-2 overflow-hidden">
            <span className="shrink-0 text-[12px] font-medium text-slate-900">{character.name}</span>
            <span className="truncate text-[12px] text-slate-700" title={summary}>{summary}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className={['mono text-[11px] tracking-[0.12em]', 'text-black/55'].join(' ')}>{label}</div>
      <div
        className={[
          'rounded-[0.95rem] border px-3.5 py-3',
          'border-black/15 bg-white',
        ].join(' ')}
      >
        <div className="text-sm text-black">{character.name}</div>
        <div className="text-xs leading-relaxed text-black/70">{summary}</div>
      </div>
    </div>
  );
}

export default function StatPanel({ characters, state, latestEval, className = '', theme = 'default' }: Props) {
  const { t } = useI18n();
  if (!state || !characters) {
    return null;
  }

  return (
    <aside
      className={[
        'min-h-0 overflow-y-auto p-3',
        className,
        theme === 'editorial'
          ? 'rounded-[0.62rem] border border-slate-300/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,251,0.96))] shadow-[0_12px_22px_rgba(15,23,42,0.04)]'
          : 'rounded-xl border border-black/30 bg-white/85 shadow-frame backdrop-blur-sm sm:rounded-2xl',
      ].join(' ')}
    >
      <div className={theme === 'editorial' ? 'space-y-3' : 'space-y-4'}>
        <div className={theme === 'editorial' ? 'space-y-2.5' : 'space-y-3'}>
          <CharacterBlock label={t('statPanel.manager')} character={characters.manager} theme={theme} />
          <CharacterBlock label={t('statPanel.buddy')} character={characters.buddy} theme={theme} />
          <div className={theme === 'editorial' ? 'grid grid-cols-[56px_minmax(0,1fr)] items-start gap-2.5' : 'space-y-1'}>
            <div className={['mono text-[11px] tracking-[0.12em]', theme === 'editorial' ? 'pt-1 text-[10px] uppercase tracking-[0.14em] text-slate-600' : 'text-black/55'].join(' ')}>
              {theme === 'editorial' ? t('statPanel.team') : `🧑‍💻 ${t('statPanel.team')}`}
            </div>
            <div className={theme === 'editorial' ? 'min-w-0 py-1' : 'space-y-2 rounded-[0.95rem] border border-black/15 bg-white px-3.5 py-3'}>
              <div className={theme === 'editorial' ? 'space-y-1.5' : 'space-y-2'}>
                {characters.team_members.map((member) => (
                  <div
                    key={`${member.id}-${member.name}`}
                    className={[
                      'flex items-baseline gap-2',
                      theme === 'editorial' ? 'min-w-0 pb-1.5 last:pb-0' : '',
                    ].join(' ')}
                  >
                    <span className={theme === 'editorial' ? 'shrink-0 text-[12px] font-medium text-slate-900' : 'text-sm text-black'}>
                      {member.name}
                    </span>
                    <span
                      className={theme === 'editorial' ? 'truncate text-[11px] leading-5 text-slate-700' : 'text-xs leading-relaxed text-black/70'}
                      title={characterSummary(member)}
                    >
                      {characterSummary(member)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className={['pt-3', theme === 'editorial' ? 'border-t border-slate-300' : 'border-t border-black/20'].join(' ')}>
          <div
            className={[
              theme === 'editorial'
                ? 'grid grid-cols-[56px_minmax(0,1fr)] items-start gap-2.5'
                : '',
            ].join(' ')}
          >
            {theme === 'editorial' ? <div className="mono pt-1 text-[10px] uppercase tracking-[0.14em] text-slate-600">State</div> : null}
            <div className={theme === 'editorial' ? 'py-1' : ''}>
            <div className={['space-y-2.5 text-xs', theme === 'editorial' ? 'text-slate-700' : 'mono text-black'].join(' ')}>
              {keys.map((key) => (
                <div key={key} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className={theme === 'editorial' ? 'text-[11px] font-medium uppercase tracking-[0.08em] text-slate-700' : ''}>
                      {statLabel(key)}
                    </span>
                    <span className={theme === 'editorial' ? 'mono text-[11px] text-slate-900' : 'text-right'}>{state[key] ?? 0}</span>
                  </div>
                  {theme === 'editorial' ? (
                    <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className={`h-full rounded-full ${statTone(key)}`}
                        style={{ width: `${Math.max(0, Math.min(10, state[key] ?? 0)) * 10}%` }}
                      />
                    </div>
                  ) : (
                    <div className="grid grid-cols-[92px_1fr_24px] items-center gap-2 mono">
                      <span>{key}</span>
                      <span>{'█'.repeat(Math.max(0, Math.min(10, state[key] ?? 0)))}{'░'.repeat(10 - Math.max(0, Math.min(10, state[key] ?? 0)))}</span>
                      <span className="text-right">{state[key] ?? 0}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
            </div>
          </div>

          <div className={['mt-4 pt-3', theme === 'editorial' ? 'border-t border-slate-300' : 'border-t border-black/20'].join(' ')}>
            <div className={theme === 'editorial' ? 'space-y-2' : ''}>
              <div className={['mb-2 mono text-[11px] tracking-[0.1em]', theme === 'editorial' ? 'text-[10px] uppercase tracking-[0.14em] text-slate-600' : 'text-black/60'].join(' ')}>
                {t('statPanel.lastScene')}
              </div>
              {latestEval ? (
                <div className={theme === 'editorial' ? 'space-y-1.5 py-1 text-[11px] leading-relaxed text-slate-800' : 'space-y-1.5 rounded-[0.68rem] border px-3 py-2.5 text-[11px] leading-relaxed text-black/80'}>
                  <div>
                    <span className={theme === 'editorial' ? 'mono uppercase tracking-[0.08em] text-slate-700' : 'text-black/60'}>{t('statPanel.eval')}:</span> {latestEval.rating} ({deltaText(latestEval.delta)})
                  </div>
                  <div>
                    <span className={theme === 'editorial' ? 'mono uppercase tracking-[0.08em] text-slate-700' : 'text-black/60'}>{t('statPanel.reason')}:</span> {latestEval.reason || '—'}
                  </div>
                </div>
              ) : (
                <div className={theme === 'editorial' ? 'py-1 text-[11px] text-slate-700' : 'rounded-[0.68rem] border px-3 py-2.5 text-[11px] text-black/55'}>
                  {t('statPanel.noEval')}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
