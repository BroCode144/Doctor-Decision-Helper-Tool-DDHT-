import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const KEY = "ddht-theme"; // "light" | "dark"; nothing saved = follow the device setting

const systemDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;

function saved() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null; // private mode: just follow the device
  }
}

/** Moon/sun button in the top bar: switches light and dark mode for every role and remembers it on this device. */
export default function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  // until the user picks one, follow the device when its setting changes
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => {
      if (!saved()) setDark(systemDark());
    };
    mq.addEventListener("change", follow);
    return () => mq.removeEventListener("change", follow);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    try {
      localStorage.setItem(KEY, next ? "dark" : "light");
    } catch {
      /* not saved in private mode; still switches for this visit */
    }
  };

  return (
    <button type="button" onClick={toggle} title={dark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={dark}
      className="rounded-xl border border-ink-200 p-2 text-ink-600 transition hover:bg-ink-100">
      {dark ? <Sun size={18} /> : <Moon size={18} />}
    </button>
  );
}
