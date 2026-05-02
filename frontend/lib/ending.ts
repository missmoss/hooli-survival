import { EndingKind, EndingPayload } from '@/lib/api';
import { Locale } from '@/lib/i18n';

type EndingViewSpec = {
  containerClassName: string;
  glowClassName: string;
  badgeClassName: string;
};

const ENDING_VIEW_SPECS: Record<EndingKind, EndingViewSpec> = {
  promoted: {
    containerClassName: 'border-emerald-900/40 bg-[linear-gradient(135deg,rgba(244,255,240,0.96),rgba(255,248,218,0.96))]',
    glowClassName: 'bg-[radial-gradient(circle_at_top,rgba(240,219,107,0.28),transparent_58%)]',
    badgeClassName: 'border-emerald-900/20 bg-white/70 text-emerald-950',
  },
  fired: {
    containerClassName: 'border-red-950/35 bg-[linear-gradient(135deg,rgba(255,244,240,0.96),rgba(244,228,224,0.98))]',
    glowClassName: 'bg-[radial-gradient(circle_at_top,rgba(127,29,29,0.16),transparent_56%)]',
    badgeClassName: 'border-red-950/15 bg-white/70 text-red-950',
  },
  quit: {
    containerClassName: 'border-slate-900/35 bg-[linear-gradient(135deg,rgba(249,247,243,0.98),rgba(235,232,226,0.98))]',
    glowClassName: 'bg-[radial-gradient(circle_at_top,rgba(15,23,42,0.12),transparent_54%)]',
    badgeClassName: 'border-slate-900/15 bg-white/70 text-slate-950',
  },
};

export type ResolvedEnding = EndingPayload & EndingViewSpec;

function _hookSeed(text: string): number {
  return Array.from(text).reduce((sum, char) => sum + char.charCodeAt(0), 0);
}

function _hookPool(kind: EndingKind, locale: Locale, context: string): string[] {
  const lower = context.toLowerCase();
  if (locale === 'zh-Hant') {
    if (lower.includes('reorg')) {
      return [
        '下午四點半的 org chart 更新，永遠不會帶來好事。',
        '你的匯報線變了，工作量當然沒有。',
      ];
    }
    if (lower.includes('pip')) {
      return [
        '每一場 check-in 都像在替自己的 badge 權限續命。',
        'PIP 的每一句話都聽起來像普通流程，直到它不是。',
      ];
    }
    if (kind === 'promoted') {
      return [
        '你把一整季的混亂，成功包裝成了升職材料。',
        'Slack 還是很吵，只是現在你得用更高職級承受它。',
      ];
    }
    if (kind === 'fired') {
      return [
        '你有故事、有成果，只是沒有 headcount。',
        '文件裡寫的是 performance，實際上寫的是出口。',
      ];
    }
    return [
      '在公司替你下結論前，你先自己收工了。',
      '最乾脆的一次職場決策，可能就是直接離開。',
    ];
  }

  if (lower.includes('reorg')) {
    return [
      'A 4:30 PM org chart update has never improved anyone’s week.',
      'Your reporting line changed. The workload did not.',
    ];
  }
  if (lower.includes('pip')) {
    return [
      'Every PIP check-in sounds routine right up until it is not.',
      'You can hear the HR platform loading in the background of every sentence.',
    ];
  }
  if (kind === 'promoted') {
    return [
      'You turned a season of chaos into promotion paperwork.',
      'Slack is still loud. You just outranked the noise this time.',
    ];
  }
  if (kind === 'fired') {
    return [
      'There were accomplishments. There was not enough headcount.',
      'The document said performance. The outcome said exit.',
    ];
  }
  return [
    'You ended the run before the org could finish the sentence.',
    'The cleanest career decision in the run was deciding when to leave it.',
  ];
}

export function buildEndingShareUrls(ending: ResolvedEnding, locale: Locale, homepageUrl: string): { x: string; threads: string; facebook: string } {
  const context = [
    ending.end_state.top_case_label,
    ending.end_state.top_case_summary,
    ending.end_state.headline,
  ]
    .filter(Boolean)
    .join(' ');
  const hooks = _hookPool(ending.kind, locale, context);
  const hook = hooks[_hookSeed(context || ending.kind) % hooks.length];
  const callToAction = 'Come play Hooli Survival!';

  const xText = hook + '\n' + callToAction;
  const threadsText = hook + '\n' + callToAction + '\n' + homepageUrl;

  return {
    x: `https://twitter.com/intent/tweet?text=${encodeURIComponent(xText)}&url=${encodeURIComponent(homepageUrl)}`,
    threads: `https://www.threads.net/intent/post?text=${encodeURIComponent(threadsText)}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(homepageUrl)}`,
  };
}

export function buildEndingShareText(ending: ResolvedEnding, locale: Locale, homepageUrl: string): string {
  const context = [
    ending.end_state.top_case_label,
    ending.end_state.top_case_summary,
    ending.end_state.headline,
  ]
    .filter(Boolean)
    .join(' ');
  const hooks = _hookPool(ending.kind, locale, context);
  const hook = hooks[_hookSeed(context || ending.kind) % hooks.length];
  return [hook, 'Come play Hooli Survival!', homepageUrl].join('\n');
}

export function resolveEndingPayload(ending: EndingPayload | null | undefined): ResolvedEnding {
  const fallback: EndingPayload = {
    kind: 'quit',
    visual_state: 'walkout',
    title_key: 'game.ending.quit.title',
    body_key: 'game.ending.quit.body',
    actions: {
      restart: true,
      share: true,
    },
    panels: {
      stats: false,
      scene_recap: false,
    },
    end_state: {
      headline: 'You walked out first.',
      share_summary: 'The run ended before the org could finish deciding what to do with you.',
      top_case_label: 'your own exit timing',
      top_case_summary: 'The cleanest decision left in the run was deciding when to stop attending it.',
      achievement_line: 'Key achievement: left while the story was still salvageable.',
      share_text: 'You walked out first.\nKey achievement: left while the story was still salvageable.',
      stats_snapshot: {},
    },
  };
  const resolved = ending || fallback;
  const viewSpec = ENDING_VIEW_SPECS[resolved.kind] || ENDING_VIEW_SPECS.quit;
  return {
    ...resolved,
    ...viewSpec,
  };
}
