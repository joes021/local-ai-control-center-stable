export const DEFAULT_THEME_ID = "dark-chocolate";
export const THEME_STORAGE_KEY = "local-ai-control-center:theme";
export const THEME_CHANGED_EVENT = "lacc-theme-changed";

export function readStoredTheme(): string {
  if (typeof window === "undefined") {
    return DEFAULT_THEME_ID;
  }
  return window.localStorage.getItem(THEME_STORAGE_KEY) || DEFAULT_THEME_ID;
}

export function applyTheme(themeId: string) {
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", themeId);
    document.body.setAttribute("data-theme", themeId);
  }
  if (typeof window !== "undefined") {
    window.localStorage.setItem(THEME_STORAGE_KEY, themeId);
    window.dispatchEvent(new CustomEvent(THEME_CHANGED_EVENT, { detail: themeId }));
  }
}
