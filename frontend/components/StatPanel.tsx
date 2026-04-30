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
};

const keys = ['tech', 'visibility', 'affinity', 'pip_potential'];

function bar(value: number): string {
  const clamped = Math.max(0, Math.min(10, value));
  return `${'█'.repeat(clamped)}${'░'.repeat(10 - clamped)}`;
}

function deltaText(delta: Record<string, number>): string {
  const keys = ['tech', 'visibility', 'affinity', 'pip_potential'];
  const parts = keys.map((k) => `${((delta[k] ?? 0) as number) >= 0 ? '+' : ''}${delta[k] ?? 0}`);
  return parts.join(' / ');
}

function CharacterBlock({
  label,
  icon,
  character,
}: {
  label: string;
  icon: string;
  character: CharacterCard;
}) {
  const summary = character.display_desc || character.personality_desc || '—';
  return (
    <div className="space-y-1">
      <div className="mono text-[11px] tracking-[0.12em] text-black/55">
        {icon} {label}
      </div>
      <div className="rounded-xl border border-black/15 bg-white px-3 py-2">
        <div className="text-sm text-black">{character.name}</div>
        <div className="text-xs leading-relaxed text-black/70">
          {summary}
        </div>
      </div>
    </div>
  );
}

export default function StatPanel({ characters, state, latestEval }: Props) {
  const { t } = useI18n();
  if (!state || !characters) {
    return null;
  }

  return (
    <aside className="min-h-0 overflow-y-auto rounded-2xl border border-black/30 bg-white/85 p-3 shadow-frame backdrop-blur-sm">
      <div className="space-y-4">
        <div className="space-y-3">
          <CharacterBlock label={t('statPanel.manager')} icon="👤" character={characters.manager} />
          <CharacterBlock label={t('statPanel.buddy')} icon="👥" character={characters.buddy} />
          <div className="space-y-1">
            <div className="mono text-[11px] tracking-[0.12em] text-black/55">🧑‍💻 {t('statPanel.team')}</div>
            <div className="space-y-2 rounded-xl border border-black/15 bg-white px-3 py-2">
              {characters.team_members.map((member) => (
                <div key={`${member.id}-${member.name}`} className="border-b border-black/10 pb-2 last:border-b-0 last:pb-0">
                  <div className="text-sm text-black">{member.name}</div>
                  <div className="text-xs leading-relaxed text-black/70">
                    {member.display_desc || member.personality_desc || '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-black/20 pt-3">
          <div className="space-y-2 mono text-xs text-black">
            {keys.map((key) => (
              <div key={key} className="grid grid-cols-[92px_1fr_24px] items-center gap-2">
                <span>{key}</span>
                <span>{bar(state[key] ?? 0)}</span>
                <span className="text-right">{state[key] ?? 0}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 border-t border-black/20 pt-3">
            <div className="mb-1 mono text-[11px] tracking-[0.1em] text-black/60">{t('statPanel.lastScene')}</div>
            {latestEval ? (
              <div className="space-y-1 text-[11px] leading-relaxed text-black/80">
                <div>
                  <span className="text-black/60">{t('statPanel.eval')}:</span> {latestEval.rating} ({deltaText(latestEval.delta)})
                </div>
                <div>
                  <span className="text-black/60">{t('statPanel.reason')}:</span> {latestEval.reason || '—'}
                </div>
              </div>
            ) : (
              <div className="text-[11px] text-black/55">{t('statPanel.noEval')}</div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
