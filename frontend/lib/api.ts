import { getBrowserId } from '@/lib/browser-id';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

type ApiError = { detail?: string };
export type Locale = 'en' | 'zh-Hant';
export type StoryOption = { id: string; text: string };
export type GeneratedBy = {
  provider?: string;
  model?: string;
} | null;
export type CharacterCard = {
  id: string;
  name: string;
  display_desc?: string;
  ai_personality_desc?: string;
  personality_desc?: string;
};
export type EndingKind = 'promoted' | 'fired' | 'quit';
export type EndingPayload = {
  kind: EndingKind;
  visual_state: 'spotlight' | 'danger' | 'walkout' | 'flat' | string;
  title_key: string;
  body_key: string;
  actions: {
    restart: boolean;
    share: boolean;
  };
  panels: {
    stats: boolean;
    scene_recap: boolean;
  };
  end_state: {
    headline: string;
    share_summary: string;
    top_case_label: string;
    top_case_summary: string;
    achievement_line: string;
    share_text: string;
    stats_snapshot: Record<string, number>;
  };
};

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const maybeError = (await res.json().catch(() => ({}))) as ApiError;
    throw new Error(maybeError.detail || `Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export type CreateSessionResponse = {
  session_id: string;
  locale: Locale;
  text: string;
  generated_by?: GeneratedBy;
  options: StoryOption[];
  start_level: string;
  player_name: string;
  scene_type: 'project' | 'event';
  scene_id: string;
  characters: {
    manager: CharacterCard;
    buddy: CharacterCard;
    team_members: CharacterCard[];
  };
  project_id: string;
  event_id: string;
  max_rounds: number;
};

export type TurnResponse = {
  text: string;
  generated_by?: GeneratedBy;
  options: StoryOption[];
  scene_ended: boolean;
  round: number;
  game_ended?: boolean;
  end_reason?: string;
  ending?: EndingPayload | null;
};

export type SessionResponse = {
  session_id: string;
  locale: Locale;
  state: Record<string, number>;
  characters: {
    manager: CharacterCard;
    buddy: CharacterCard;
    team_members: CharacterCard[];
  };
  current_scene_type: 'project' | 'event';
  current_scene_id: string;
  current_event_id: string;
  current_project_id: string;
  current_opening_text: string;
  current_generated_by?: GeneratedBy;
  current_options: StoryOption[];
  status: string;
  end_reason: string | null;
  ending: EndingPayload | null;
  round: number;
  max_rounds: number;
  latest_eval: {
    scene_type: 'project' | 'event';
    scene_id: string;
    rating: 'good' | 'neutral' | 'bad' | string;
    reason: string | null;
    delta: Record<string, number>;
  } | null;
};

export type NextSceneResponse =
  | { ready: false }
  | {
      ready: true;
      text: string;
      generated_by?: GeneratedBy;
      options: StoryOption[];
      scene_type: 'project' | 'event';
      scene_id: string;
      event_id: string;
      project_id: string;
    };

export async function createSession(playerName?: string, locale?: Locale): Promise<CreateSessionResponse> {
  const browserId = getBrowserId();
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Office-Sim-Browser-Id': browserId,
    },
    body: JSON.stringify({
      player_name: (playerName || '').trim() || undefined,
      locale,
    }),
  });
  return parseJson<CreateSessionResponse>(res);
}

export type DevPerfReviewScenario = 'regular' | 'promo' | 'pip';

export async function devCreatePerfReviewFixture(
  playerName?: string,
  scenario: DevPerfReviewScenario = 'regular',
  locale?: Locale,
): Promise<CreateSessionResponse> {
  const browserId = getBrowserId();
  const res = await fetch(`${API_BASE}/dev/sessions/perf-review-fixture`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-Office-Sim-Browser-Id': browserId,
    },
    body: JSON.stringify({
      player_name: (playerName || '').trim() || undefined,
      scenario,
      locale,
    }),
  });
  return parseJson<CreateSessionResponse>(res);
}

export async function sendTurn(sessionId: string, message: string): Promise<TurnResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/turn`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  return parseJson<TurnResponse>(res);
}

export async function getSession(sessionId: string): Promise<SessionResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
  });
  return parseJson<SessionResponse>(res);
}

export async function getNextScene(sessionId: string): Promise<NextSceneResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/next-scene`, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
  });
  return parseJson<NextSceneResponse>(res);
}
