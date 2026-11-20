import { useEffect, useRef } from "react";
import { X } from "lucide-react";

/**
 * Pop-up dialog. Escape or a click outside closes it.
 *
 * Focus moves to the dialog only once, when it opens. (The old version re-ran its effect whenever `onClose`
 * changed. Screens pass a new arrow function on every render, so each keystroke in a text box inside the dialog
 * pulled the cursor out of the box.) The latest `onClose` is kept in a ref so Escape still uses it.
 * Original kept in frontend/backups/ui-index.before-modal-fix.jsx.
 */
export function Modal({ open, onClose, title, children, footer, size = "md" }) {
  const ref = useRef(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onCloseRef.current?.();
    document.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;
  const sizes = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl", xl: "max-w-5xl" };
  return (
    <div
      className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-ink-950/50 p-4"
      role="presentation"
      onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <div ref={ref} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} className={`flex max-h-[88vh] w-full flex-col overflow-hidden rounded-2xl bg-white shadow-2xl outline-none ${sizes[size]}`}>
        <div className="flex shrink-0 items-center justify-between border-b border-ink-100 px-6 py-4">
          <h2 className="font-display text-lg font-bold text-ink-900">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close dialog" className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-100 hover:text-ink-700">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex shrink-0 items-center justify-end gap-3 border-t border-ink-100 px-6 py-4">{footer}</div>}
      </div>
    </div>
  );
}
