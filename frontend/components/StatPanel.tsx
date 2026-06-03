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

function CharacterBlock({ label, character }: { label: string; character: CharacterCard }) {
  const summary = characterSummary(character);
  return (
    <div className="grid grid-cols-[56px_minmax(0,1fr)] items-start gap-2.5">
      <div className="mono pt-1 text-[10px] uppercase tracking-[0.14em] text-slate-600">{label}</div>
      <div className="min-w-0 py-1">
        <div className="flex items-baseline gap-2 overflow-hidden">
          <span className="shrink-0 text-[12px] font-medium text-slate-900">{character.name}</span>
          <span className="truncate text-[12px] text-slate-700" title={summary}>
            {summary}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function StatPanel({ characters, state, latestEval, className = '' }: Props) {
  const { t } = useI18n();
  if (!state || !characters) {
    return null;
  }

  return (
    <aside
      className={[
        'min-h-0 overflow-y-auto rounded-[0.62rem] border border-slate-300/90 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,251,0.96))] p-3 shadow-[0_12px_22px_rgba(15,23,42,0.04)]',
        className,
      ].join(' ')}
    >
      <div className="space-y-3">
        <div className="space-y-2.5">
          <CharacterBlock label={t('statPanel.manager')} character={characters.manager} />
          <CharacterBlock label={t('statPanel.buddy')} character={characters.buddy} />
          <div className="grid grid-cols-[56px_minmax(0,1fr)] items-start gap-2.5">
            <div className="mono pt-1 text-[10px] uppercase tracking-[0.14em] text-slate-600">{t('statPanel.team')}</div>
            <div className="min-w-0 py-1">
              <div className="space-y-1.5">
                {characters.team_members.map((member) => (
                  <div key={`${member.id}-${member.name}`} className="flex min-w-0 items-baseline gap-2 pb-1.5 last:pb-0">
                    <span className="shrink-0 text-[12px] font-medium text-slate-900">{member.name}</span>
                    <span className="truncate text-[12px] leading-5 text-slate-700" title={characterSummary(member)}>
                      {characterSummary(member)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="border-t border-slate-300 pt-3">
          <div className="grid grid-cols-[56px_minmax(0,1fr)] items-start gap-2.5">
            <div className="mono pt-1 text-[10px] uppercase tracking-[0.14em] text-slate-600">State</div>
            <div className="py-1">
              <div className="space-y-2.5 text-xs text-slate-700">
                {keys.map((key) => (
                  <div key={key} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[11px] font-medium uppercase tracking-[0.08em] text-slate-700">
                        {statLabel(key)}
                      </span>
                      <span className="mono text-[11px] text-slate-900">{state[key] ?? 0}</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className={`h-full rounded-full ${statTone(key)}`}
                        style={{ width: `${Math.max(0, Math.min(10, state[key] ?? 0)) * 10}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 border-t border-slate-300 pt-3">
            <div className="space-y-2">
              <div className="mb-2 mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
                {t('statPanel.lastScene')}
              </div>
              {latestEval ? (
                <div className="space-y-1.5 py-1 text-[11px] leading-relaxed text-slate-800">
                  <div>
                    <span className="mono uppercase tracking-[0.08em] text-slate-700">{t('statPanel.eval').toUpperCase()}:</span>{' '}
                    {latestEval.rating} ({deltaText(latestEval.delta)})
                  </div>
                  <div>
                    <span className="mono uppercase tracking-[0.08em] text-slate-700">{t('statPanel.reason').toUpperCase()}:</span>{' '}
                    {latestEval.reason || '—'}
                  </div>
                </div>
              ) : (
                <div className="py-1 text-[11px] text-slate-700">{t('statPanel.noEval')}</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
