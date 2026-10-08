import type { ReactNode } from "react";

/** The frame of the public pages (sign in, register, reset...): the product lockup, then this page's own h1,
 *  so each page has a distinct heading instead of "QEOS" everywhere. */
export default function AuthShell({ title, subtitle = true, children }: { title: string; subtitle?: boolean; children: ReactNode }) {
  return (
    <div className="page page-narrow">
      <p className="brand-name">QEOS</p>
      {subtitle && <p className="brand-subtitle">Quality Engineering OS</p>}
      <h1 className="auth-title">{title}</h1>
      {children}
    </div>
  );
}
