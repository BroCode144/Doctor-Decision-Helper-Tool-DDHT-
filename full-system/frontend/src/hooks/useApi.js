import { useCallback, useEffect, useRef, useState } from "react";

/** Run an async loader, tracking data / loading / error, with reload().
    `pollMs` refreshes quietly in the background (no loading spinner) while the page is open. */
export function useApi(loader, deps = [], { pollMs } = {}) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const seq = useRef(0);

  const run = useCallback(async (quiet) => {
    const id = ++seq.current;
    if (!quiet) setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await loaderRef.current();
      if (id === seq.current) setState({ data, loading: false, error: null });
    } catch (error) {
      if (id === seq.current && !quiet) setState({ data: null, loading: false, error });
    }
  }, []);
  const reload = useCallback(() => run(false), [run]);

  useEffect(() => {
    run(false);
    if (!pollMs) return undefined;
    const t = setInterval(() => document.visibilityState === "visible" && run(true), pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, pollMs]);

  return { ...state, reload, refresh: () => run(true) };
}
