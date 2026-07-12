import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ActivityComponent = "all" | "codex_lb" | "codexneo" | "provider";

type CodexNeoActivityPageProps = {
  contents: string;
  disabled: boolean;
  onClear: () => void | Promise<unknown>;
  onRefresh: () => void | Promise<unknown>;
};

export function CodexNeoActivityPage({ contents, disabled, onClear, onRefresh }: CodexNeoActivityPageProps) {
  const [component, setComponent] = useState<ActivityComponent>("all");
  const [accountFilter, setAccountFilter] = useState("");
  const [search, setSearch] = useState("");
  const [errorsOnly, setErrorsOnly] = useState(false);
  const filteredContents = useMemo(() => {
    const accountNeedle = accountFilter.trim().toLowerCase();
    const searchNeedle = search.trim().toLowerCase();
    return contents
      .split(/\r?\n/)
      .filter(Boolean)
      .filter((line) => {
        const lower = line.toLowerCase();
        if (component !== "all" && !lower.includes(`[${component}]`)) return false;
        if (accountNeedle && !lower.includes(accountNeedle)) return false;
        if (searchNeedle && !lower.includes(searchNeedle)) return false;
        if (errorsOnly && !/(?:\b4\d\d\b|\b5\d\d\b|error|failed|unavailable)/i.test(line)) return false;
        return true;
      })
      .join("\n");
  }, [accountFilter, component, contents, errorsOnly, search]);

  return (
    <section
      data-testid="codexneo-activity-page"
      className="flex h-[calc(100dvh-19rem)] flex-col gap-4"
      aria-labelledby="codexneo-activity-heading"
    >
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="codexneo-activity-heading" className="text-xl font-semibold">Activity log</h2>
          <p className="text-sm text-muted-foreground">
            Combined safe activity from Codex LB, CodexNeo, and the CodexGO provider.
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" disabled={disabled} onClick={() => void onRefresh()}>
            Refresh
          </Button>
          <Button type="button" variant="destructive" disabled={disabled} onClick={() => void onClear()}>
            Clear
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border/70 bg-background/60">
        <div className="sticky top-0 z-10 shrink-0 grid gap-2 border-b border-border/70 bg-background/95 p-3 backdrop-blur md:grid-cols-[12rem_1fr_1fr_auto]">
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Component
            <select
              aria-label="Activity component"
              className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
              value={component}
              onChange={(event) => setComponent(event.target.value as ActivityComponent)}
            >
              <option value="all">All components</option>
              <option value="codex_lb">Codex LB</option>
              <option value="codexneo">CodexNeo</option>
              <option value="provider">Provider</option>
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Account
            <Input
              aria-label="Activity account"
              value={accountFilter}
              onChange={(event) => setAccountFilter(event.target.value)}
              placeholder="Email or account id"
            />
          </label>
          <label className="space-y-1 text-xs font-medium text-muted-foreground">
            Search
            <Input
              aria-label="Search activity"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Event or result"
            />
          </label>
          <label className="flex h-9 items-center gap-2 self-end text-sm">
            <input
              aria-label="Errors only"
              type="checkbox"
              checked={errorsOnly}
              onChange={(event) => setErrorsOnly(event.target.checked)}
            />
            Errors only
          </label>
        </div>
        <pre
          data-testid="codexneo-activity-log"
          className="min-h-72 flex-1 overflow-auto bg-slate-950 p-4 font-mono text-xs leading-relaxed whitespace-pre-wrap text-slate-100"
        >
          {filteredContents || "No activity matches the current filters."}
        </pre>
        <div className="shrink-0 border-t border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-200">
          Events are retained for 24 hours. Cleanup runs in the backend even while this page is closed and never deletes usage statistics.
        </div>
      </div>
    </section>
  );
}
