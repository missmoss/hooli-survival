'use client';

import { useI18n } from '@/lib/i18n';

type SceneTransitionProps = {
  message?: string;
};

export default function SceneTransition({ message }: SceneTransitionProps) {
  const { t } = useI18n();
  return (
    <div className="mt-4 rounded-xl border border-dashed border-black/40 bg-white/70 px-4 py-3 text-sm text-black/70 mono">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-black" />
          <span>⏳ {message || t('transition.settling')}</span>
        </div>
      </div>
    </div>
  );
}
