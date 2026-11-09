import type { ReactNode } from "react";

export function FormField({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: string; children: ReactNode }) {
  return <div className="field"><label htmlFor={id}>{label}</label>{children}{hint && <p className="hint" id={`${id}-hint`}>{hint}</p>}{error && <p className="field-error" id={`${id}-error`}>{error}</p>}</div>;
}
