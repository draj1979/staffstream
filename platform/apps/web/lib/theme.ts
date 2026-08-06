const THEME_KEY = "staffstream.theme";

export type ThemePreference = "light" | "dark" | "system";

export function getThemePreference(): ThemePreference {
  if (typeof window === "undefined") return "system";
  const stored = localStorage.getItem(THEME_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

export function setThemePreference(pref: ThemePreference) {
  if (typeof window === "undefined") return;
  if (pref === "system") {
    localStorage.removeItem(THEME_KEY);
    document.documentElement.removeAttribute("data-theme");
  } else {
    localStorage.setItem(THEME_KEY, pref);
    document.documentElement.setAttribute("data-theme", pref);
  }
}
