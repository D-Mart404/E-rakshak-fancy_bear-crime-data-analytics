/** Single source of truth for product information architecture. */

export type PrimaryNavId = "overview" | "cases" | "evidence" | "insights" | "reports";

export type NavTab = {
  href: string;
  label: string;
  short: string;
  dataType: string;
};

export type PrimaryNavItem = {
  id: PrimaryNavId;
  href: string;
  label: string;
  hint: string;
  icon: string;
  match: (pathname: string) => boolean;
  tabs?: NavTab[];
};

export const PRIMARY_NAV: PrimaryNavItem[] = [
  {
    id: "overview",
    href: "/",
    label: "Overview",
    hint: "Case at a glance",
    icon: "⌂",
    match: (p) => p === "/",
  },
  {
    id: "cases",
    href: "/cases",
    label: "Cases",
    hint: "All FIR workspaces",
    icon: "▣",
    match: (p) => p === "/cases" || p.startsWith("/cases/"),
  },
  {
    id: "evidence",
    href: "/entities",
    label: "Evidence",
    hint: "Raw records",
    icon: "▤",
    match: (p) =>
      ["/entities", "/transactions", "/telecom", "/ipdr", "/documents"].some(
        (base) => p === base || p.startsWith(`${base}/`)
      ),
    tabs: [
      {
        href: "/entities",
        label: "People & accounts",
        short: "People",
        dataType: "Entities",
      },
      {
        href: "/transactions",
        label: "Bank money",
        short: "Money",
        dataType: "Transactions",
      },
      {
        href: "/telecom",
        label: "Phone calls (CDR)",
        short: "Calls",
        dataType: "CDR",
      },
      {
        href: "/ipdr",
        label: "Internet (IPDR)",
        short: "Internet",
        dataType: "IPDR",
      },
      {
        href: "/documents",
        label: "Uploaded files",
        short: "Files",
        dataType: "Documents",
      },
    ],
  },
  {
    id: "insights",
    href: "/findings",
    label: "Insights",
    hint: "Analysis tools",
    icon: "◈",
    match: (p) =>
      ["/findings", "/network", "/timeline", "/sankey", "/leaderboard"].some(
        (base) => p === base || p.startsWith(`${base}/`)
      ) || p.startsWith("/investigation/"),
    tabs: [
      {
        href: "/findings",
        label: "Call → money links",
        short: "Links",
        dataType: "Correlations",
      },
      {
        href: "/network",
        label: "Network map",
        short: "Network",
        dataType: "Graph",
      },
      {
        href: "/timeline",
        label: "Timeline",
        short: "Timeline",
        dataType: "Events over time",
      },
      {
        href: "/sankey",
        label: "Money flow",
        short: "Flow",
        dataType: "Fund movement",
      },
      {
        href: "/leaderboard",
        label: "Priority suspects",
        short: "Priority",
        dataType: "Risk ranking",
      },
    ],
  },
  {
    id: "reports",
    href: "/str",
    label: "Reports",
    hint: "STR & audit",
    icon: "≣",
    match: (p) =>
      ["/str", "/audit"].some((base) => p === base || p.startsWith(`${base}/`)),
    tabs: [
      {
        href: "/str",
        label: "STR / case report",
        short: "STR",
        dataType: "Report",
      },
      {
        href: "/audit",
        label: "Activity log",
        short: "Audit",
        dataType: "Audit trail",
      },
    ],
  },
];

export function resolvePrimary(pathname: string): PrimaryNavItem {
  return (
    PRIMARY_NAV.find((item) => item.match(pathname)) ?? PRIMARY_NAV[0]
  );
}

export function resolveTab(pathname: string): NavTab | null {
  const primary = resolvePrimary(pathname);
  if (!primary.tabs?.length) return null;
  return (
    primary.tabs.find(
      (t) => pathname === t.href || pathname.startsWith(`${t.href}/`)
    ) ?? primary.tabs[0]
  );
}

export const JUMP_TARGETS = [
  { href: "/", label: "Overview", keywords: "home dashboard" },
  { href: "/cases", label: "All cases", keywords: "fir case" },
  { href: "/entities", label: "People & accounts", keywords: "entity suspect" },
  { href: "/transactions", label: "Bank transactions", keywords: "money credit debit" },
  { href: "/telecom", label: "Phone calls CDR", keywords: "call phone cdr" },
  { href: "/ipdr", label: "Internet IPDR", keywords: "ip internet ipdr" },
  { href: "/documents", label: "Upload documents", keywords: "file upload pdf" },
  { href: "/findings", label: "Call → money links", keywords: "correlation finding" },
  { href: "/network", label: "Network map", keywords: "graph connection" },
  { href: "/timeline", label: "Timeline", keywords: "time episode" },
  { href: "/sankey", label: "Money flow", keywords: "sankey flow" },
  { href: "/leaderboard", label: "Priority suspects", keywords: "risk lead" },
  { href: "/str", label: "STR report", keywords: "report str" },
  { href: "/audit", label: "Activity log", keywords: "audit log" },
];
