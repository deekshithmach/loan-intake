"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "Create application" },
  { href: "/in-review", label: "In review" },
  { href: "/approved", label: "Approved" },
  { href: "/rejected", label: "Rejected" },
  { href: "/models", label: "Model stats" },
];

export function Tabs() {
  const path = usePathname();
  return (
    <nav className="mx-auto flex max-w-7xl gap-1 px-4" aria-label="Sections">
      {TABS.map((t) => {
        const active = t.href === "/" ? path === "/" : path.startsWith(t.href);
        return (
          <Link
            key={t.href}
            href={t.href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition ${
              active ? "border-zinc-900 font-medium text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-900"
            }`}
          >
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
