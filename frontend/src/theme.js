const KEY = "airline.theme";
const MODES = ["light", "dark", "system"];

export function getTheme() {
  try {
    const saved = localStorage.getItem(KEY);
    return MODES.includes(saved) ? saved : "light";
  } catch {
    return "light";
  }
}

function resolve(mode) {
  if (mode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return mode;
}

function apply(mode) {
  document.documentElement.setAttribute("data-theme", resolve(mode));
}

export function setTheme(mode) {
  if (!MODES.includes(mode)) return;
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    // storage unavailable: the theme still applies for this visit
  }
  apply(mode);
}

// While in "system" mode, follow the operating system when it changes.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (getTheme() === "system") apply("system");
});

apply(getTheme()); // applies itself on import