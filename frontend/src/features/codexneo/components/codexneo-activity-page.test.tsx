import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CodexNeoActivityPage } from "./codexneo-activity-page";

describe("CodexNeoActivityPage", () => {
  it("uses the available viewport while keeping the activity stream internally scrollable", () => {
    render(
      <CodexNeoActivityPage
        contents="[2026-07-12T10:00:00] [codex_lb] Request routed -> 200"
        disabled={false}
        onClear={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByTestId("codexneo-activity-page")).toHaveClass("h-[calc(100dvh-19rem)]");
    expect(screen.getByTestId("codexneo-activity-log")).toHaveClass("flex-1", "overflow-auto");
    expect(screen.getByTestId("codexneo-activity-log")).not.toHaveClass("max-h-[32rem]");
  });

  it("filters the combined stream by component, account, error, and search text", async () => {
    const user = userEvent.setup();
    render(
      <CodexNeoActivityPage
        contents={[
          "[2026-07-12T10:00:00] [codex_lb] Request routed account=alpha -> 200",
          "[2026-07-12T10:01:00] [codexneo] Backup saved account=beta",
          "[2026-07-12T10:02:00] [provider] Refresh failed account=alpha -> 502",
        ].join("\n")}
        disabled={false}
        onClear={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Activity component"), "provider");
    await user.type(screen.getByLabelText("Activity account"), "alpha");
    await user.click(screen.getByLabelText("Errors only"));
    await user.type(screen.getByLabelText("Search activity"), "refresh");

    expect(screen.getByText(/Refresh failed account=alpha/)).toBeInTheDocument();
    expect(screen.queryByText(/Request routed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Backup saved/)).not.toBeInTheDocument();
  });
});
