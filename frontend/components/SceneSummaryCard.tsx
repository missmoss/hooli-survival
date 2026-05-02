'use client';

import { LatestEval } from '@/lib/api';
import { SITE_URL } from '@/lib/config';
import { Locale, useI18n } from '@/lib/i18n';

type Props = {
  evaluation: LatestEval;
  onContinue: () => void;
};

const X_QUOTES: Record<Locale, string[]> = {
  en: [
    'You spoke three sentences in thirty minutes.\nTwo were "mm-hmm."',
    '"Our top priority is solving user problems."\n\nIt slowly dawns on you: the owner was onboarded last week.',
    'Free food is free food.\nThis is the closest thing to a belief system you have left.',
    "Where's the promotion scope? You look up, as if the ceiling might have answers.\nA ceiling AC unit drips on your face.",
  ],
  'zh-Hant': [
    'PM 可以連講一個小時，走出會議室，你還是搞不清楚明天要先做哪張 ticket。',
    '你吃完公司的免費午餐，雖然又是千篇一律的「健康均衡餐」，但不用付錢就是快樂。',
    '這年頭，如果有個不遲到的 PM，你甚至會偷偷懷疑這人是不是太閒。',
    '到底哪裡有升職的 scope？你抬頭想問天，結果剛好被外漏的冷氣水滴了一臉。',
  ],
};

const THREADS_QUOTES: Record<Locale, string[]> = {
  en: [
    'You spoke three sentences in thirty minutes.\nTwo were "mm-hmm."',
    '"Our top priority is solving user problems."\n\nIt slowly dawns on you: the owner was onboarded last week.\n\n"Our top priority is solving user problems" isn\'t a commitment. It\'s a default line.',
    'Kevin pulls up three Slack channels as evidence. One is #random.\n\nHis analysis connects org restructuring rumors, a cafeteria menu change, and a VP\'s LinkedIn post into a theory so internally consistent you almost forget none of it is real.',
    "Shiva — the quiet coworker who barely speaks, who silently eats through every team lunch like a monk observing a vow — drifts past your desk and drops a single sentence:\n\n\"Eggdrop protein API. That's the answer you want.\"\n\nNo context. No follow-up. Already walking away.",
    'Free food is free food.\nThis is the closest thing to a belief system you have left.',
    "Where's the promotion scope? You look up, as if the ceiling might have answers.\nA ceiling AC unit drips on your face.\n\nYou wipe away what could be tears, sweat, or HVAC water, and decide...",
    'Jimmy sits down and starts a sequence:\n\n"Let me get some water first."\n"The boss cares about this. Absolutely promotion material."\n"Everything else can be pushed to later milestones. You know what I mean, right?"\n\nOne sip of water fully restores Jimmy\'s HP.',
  ],
  'zh-Hant': [
    'PM 可以連講一個小時，走出會議室，你還是搞不清楚明天要先做哪張 ticket。\n同事總是在 deadline 的前一天消失，領導階層每三個月換一次方向。',
    '你吃完公司的免費午餐，雖然又是千篇一律的「健康均衡餐」，但不用付錢就是快樂。\n昏昏欲睡澱粉暈的下午，你無意識地確認第一百次信箱有沒有新信件。',
    '隔壁座位的八卦王 Kevin 鬼鬼祟祟地過來拍你肩膀：「聽說隔壁組的 Larry 突然收到一封高層 1:1 邀請，我們 org 是不是要起飛了？」\n你聽著他天花亂墜引用不同 slack channel 的消息，煞有其事地佐證起飛的推測不是幻想。',
    '這次 Sprint 拿到的專案，經典本組風味：PM 語焉不詳，客戶抱怨連連，開發時間還只給兩週。\n毫無技術深度，拿去請教 Tech Lead 裝用功，他都懶得理你的那種。\n又是一個放進 performance review 都不夠格的專案。',
    '到底哪裡有升職的 scope？你抬頭想問天，結果剛好被外漏的冷氣水滴了一臉。\n擦乾不知道是爬滿淚水、汗水、還是冷氣水的臉，你決定⋯⋯',
    'AI digest 跳出今日摘要：「All Hands 大會！Gavin 會親自回答！」\n已經連續一個禮拜都摘要同一則訊息了，實在很難釐清這是 Gavin 技術性蓋版？還是 AI digest 實力發揮。',
    '開會遲到五分鐘的 PM 已是家常便飯，你等。這年頭，如果有個不遲到的 PM，你甚至會偷偷懷疑這人是不是太閒。 ',
  ],
};

function pickFromPool<T>(pool: T[], seed: string): T {
  const hash = Array.from(seed).reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return pool[hash % pool.length];
}

function buildShareUrls(evaluation: LatestEval, siteUrl: string, locale: Locale) {
  const seed = evaluation.scene_id + evaluation.rating;
  const xQuote = pickFromPool(X_QUOTES[locale], seed);
  const threadsQuote = pickFromPool(THREADS_QUOTES[locale], seed);
  const suffix = '\n\nCome play Hooli Survival';

  const xText = xQuote + suffix;
  const threadsText = threadsQuote + suffix + '\n' + siteUrl;

  const x = `https://twitter.com/intent/tweet?text=${encodeURIComponent(xText)}&url=${encodeURIComponent(siteUrl)}`;
  const threads = `https://www.threads.net/intent/post?text=${encodeURIComponent(threadsText)}`;
  const facebook = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(siteUrl)}`;

  return { x, threads, facebook };
}

const DELTA_KEYS = ['tech', 'visibility', 'affinity', 'pip_potential'] as const;

const HEADLINES: Record<Locale, Record<'good' | 'neutral' | 'bad', string[]>> = {
  en: {
    good: ['Nice save.', 'Management noticed.', 'You looked expensive in a good way.'],
    neutral: ['You survived. Barely.', 'No one escalated it. Yet.', 'That could have gone worse.'],
    bad: ['That got messy.', 'Not your cleanest moment.', 'Someone is updating a spreadsheet about this.'],
  },
  'zh-Hant': {
    good: ['收得不錯。', '管理層有看到。', '這次看起來像是高成本人才。'],
    neutral: ['你活下來了。暫時。', '至少還沒被 escalate。', '還行，沒更糟。'],
    bad: ['這次有點亂。', '不是你最乾淨的一次。', '有人正在更新一張關於你的表。'],
  },
};

function pickHeadline(locale: Locale, evaluation: LatestEval): string {
  const rating = evaluation.rating === 'good' || evaluation.rating === 'bad' ? evaluation.rating : 'neutral';
  const candidates = HEADLINES[locale][rating];
  const score = DELTA_KEYS.reduce((total, key, index) => total + ((evaluation.delta[key] ?? 0) * (index + 2)), 0);
  return candidates[Math.abs(score) % candidates.length];
}

function deltaLabel(locale: Locale, key: string): string {
  const labels: Record<Locale, Record<string, string>> = {
    en: {
      tech: 'Tech',
      visibility: 'Visibility',
      affinity: 'Affinity',
      pip_potential: 'PIP Risk',
    },
    'zh-Hant': {
      tech: '技術',
      visibility: '能見度',
      affinity: '關係',
      pip_potential: 'PIP 風險',
    },
  };
  return labels[locale][key] || key;
}

function ratingLabel(locale: Locale, rating: string): string {
  const labels: Record<Locale, Record<string, string>> = {
    en: {
      good: 'good',
      neutral: 'neutral',
      bad: 'bad',
    },
    'zh-Hant': {
      good: '好',
      neutral: '普通',
      bad: '糟',
    },
  };
  return labels[locale][rating] || labels[locale].neutral;
}

function deltaEntries(evaluation: LatestEval, locale: Locale): string[] {
  const values = DELTA_KEYS
    .map((key) => {
      const value = Number(evaluation.delta[key] ?? 0);
      if (!value) {
        return null;
      }
      return `${value > 0 ? '+' : ''}${value} ${deltaLabel(locale, key)}`;
    })
    .filter((entry): entry is string => Boolean(entry));
  return values.length > 0 ? values : [locale === 'zh-Hant' ? '沒有數值變動' : 'No stat changes'];
}

export default function SceneSummaryCard({ evaluation, onContinue }: Props) {
  const { locale, t } = useI18n();
  const deltas = deltaEntries(evaluation, locale);
  const shareUrls = buildShareUrls(evaluation, SITE_URL, locale);

  return (
    <section className="mt-3 rounded-[1.4rem] border border-black/30 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,248,248,0.92))] p-4 shadow-frame sm:mt-4 sm:p-5">
      <div className="mono inline-flex rounded-full border border-black/20 bg-black/[0.03] px-2.5 py-1 text-[11px] tracking-[0.16em] text-black/58">
        {t('summary.eyebrow')}
      </div>
      <h2 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-black sm:text-2xl">
        {pickHeadline(locale, evaluation)}
      </h2>
      <p className="mono mt-2 text-xs tracking-[0.14em] text-black/52">
        {t('summary.rating')}: {ratingLabel(locale, evaluation.rating)}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {deltas.map((entry) => (
          <div
            key={entry}
            className="rounded-full border border-black/15 bg-black/[0.03] px-3 py-1.5 text-sm text-black/82"
          >
            {entry}
          </div>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          onClick={onContinue}
          className="mono rounded-xl border border-black bg-black px-4 py-3 text-sm text-white transition hover:bg-white hover:text-black sm:w-auto"
        >
          {t('summary.continue')}
        </button>
        <span className="mono text-[11px] text-black/38">{t('summary.share')}</span>
        {[
          { href: shareUrls.x, domain: 'x.com', label: 'X' },
          { href: shareUrls.threads, domain: 'threads.net', label: 'Threads' },
          { href: shareUrls.facebook, domain: 'facebook.com', label: 'Facebook' },
        ].map(({ href, domain, label }) => (
          <a
            key={domain}
            href={href}
            target="_blank"
            rel="noreferrer"
            title={label}
            className="flex h-6 w-6 items-center justify-center rounded-md border border-black/15 bg-white/70 opacity-60 transition hover:opacity-100"
          >
            <img
              src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
              width={14}
              height={14}
              alt={label}
            />
          </a>
        ))}
      </div>
    </section>
  );
}
