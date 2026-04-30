const STORAGE_KEY = 'hooli:browser-id';

function createBrowserId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `br_${crypto.randomUUID().replace(/-/g, '')}`;
  }
  return `br_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export function getBrowserId(): string {
  if (typeof window === 'undefined') {
    return 'server-render';
  }

  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) {
    return existing;
  }

  const created = createBrowserId();
  window.localStorage.setItem(STORAGE_KEY, created);
  return created;
}
