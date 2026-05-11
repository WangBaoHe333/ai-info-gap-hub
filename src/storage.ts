const FAVORITES_KEY = "ai-info-gap-favorites-v1";

export function readFavorites(): Set<string> {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    const ids = raw ? (JSON.parse(raw) as string[]) : [];
    return new Set(ids);
  } catch {
    return new Set();
  }
}

export function writeFavorites(ids: Set<string>): void {
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...ids]));
}
