'use client';

import { useI18n } from '@/lib/i18n';

type SceneTransitionProps = {
  message?: string;
};

export default function SceneTransition({ message }: SceneTransitionProps) {
  const { t } = useI18n();
  const copy = message || t('transition.settling');
  return (
    <div className="mt-4 px-1 py-1 text-[12px] mono text-slate-700">
      <div className="px-1 py-3">
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-slate-300" />
          <div className="inline-flex items-center px-1 py-1">
            <span className="text-[11px] uppercase tracking-[0.18em] text-slate-700">{copy}</span>
          </div>
          <div className="h-px flex-1 bg-slate-300" />
        </div>
      </div>
    </div>
  );
}
