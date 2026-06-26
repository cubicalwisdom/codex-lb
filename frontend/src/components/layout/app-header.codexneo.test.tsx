import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/utils";

import { AppHeader } from "./app-header";

describe("AppHeader CodexNeo navigation", () => {
  it("includes the CodexNeo primary navigation tab", () => {
    renderWithProviders(<AppHeader onLogout={vi.fn()} />);

    expect(screen.getByRole("link", { name: "CodexNeo" })).toHaveAttribute("href", "/codexneo");
  });
});
