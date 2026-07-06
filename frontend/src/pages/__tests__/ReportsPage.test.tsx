import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";

import { ReportsPage } from "@/pages/ReportsPage";
import { server } from "@/test/server";
import { summaryFixture } from "@/test/fixtures";
import { renderWithProviders } from "@/test/utils";

// The V1 archive's clutter control (Session 42): deleting a stored report must
// be gated behind an explicit confirmation, and confirming must call the real
// DELETE endpoint and drop the row.
describe("ReportsPage — delete with confirmation", () => {
  it("deletes a report only after the confirmation is accepted", async () => {
    let deleted = false;
    server.use(
      http.get("/api/v1/analyses", () => HttpResponse.json(deleted ? [] : [summaryFixture])),
      http.delete(`/api/v1/analyses/${summaryFixture.id}`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<ReportsPage />);

    await user.click(await screen.findByLabelText(/delete report/i));
    // Confirmation gate: nothing deleted yet.
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
    expect(deleted).toBe(false);

    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await waitFor(() => expect(deleted).toBe(true));
    await waitFor(() =>
      expect(screen.queryByLabelText(/delete report/i)).not.toBeInTheDocument(),
    );
  });

  it("cancel closes the confirmation without deleting", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ReportsPage />);

    await user.click(await screen.findByLabelText(/delete report/i));
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(screen.queryByText(/cannot be undone/i)).not.toBeInTheDocument();
    // The row is still there.
    expect(screen.getByLabelText(/delete report/i)).toBeInTheDocument();
  });
});
