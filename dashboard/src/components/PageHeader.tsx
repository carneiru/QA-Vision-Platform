import { ReactNode, Ref } from "react";
import { Link } from "react-router-dom";

/** A view tab: the current one has no `to`. Links resolve against the current path, like `<Link relative="path">`. */
export interface PageTab {
  label: string;
  to?: string;
}

interface Props {
  /** The page name; the breadcrumb carries the org and project. */
  title: string;
  subtitle?: ReactNode;
  /** At most one primary button; the rest secondary. They wrap under the title on phones. */
  actions?: ReactNode;
  tabs?: PageTab[];
  headingRef?: Ref<HTMLHeadingElement>;
}

/** The head of every signed-in page: one h1 (focused after a navigation), an optional subtitle,
 *  actions on the right and optional view tabs underneath. */
export default function PageHeader({ title, subtitle, actions, tabs, headingRef }: Props) {
  return (
    <div className="page-head">
      <div className="page-head-row">
        <div className="page-head-text">
          <h1 ref={headingRef} tabIndex={-1}>{title}</h1>
          {subtitle != null && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {actions != null && <div className="page-header-actions button-row">{actions}</div>}
      </div>
      {tabs && tabs.length > 0 && (
        <nav className="view-tabs" aria-label={`${title} views`}>
          {tabs.map((t) =>
            t.to === undefined ? (
              <span key={t.label} aria-current="page">{t.label}</span>
            ) : (
              <Link key={t.label} to={t.to} relative="path">{t.label}</Link>
            ),
          )}
        </nav>
      )}
    </div>
  );
}
