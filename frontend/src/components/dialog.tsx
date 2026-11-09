"use client";
import { useEffect, useRef, type ReactNode } from "react";

export function Dialog({ open, title, onClose, children, footer }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    const previous = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => { dialog.close(); previous?.focus(); };
  }, [open]);
  return <dialog ref={ref} aria-label={title} onCancel={(event) => { event.preventDefault(); onClose(); }}><h2>{title}</h2>{children}<div className="actions dialog-footer">{footer}<button type="button" className="secondary" onClick={onClose}>Tutup</button></div></dialog>;
}
