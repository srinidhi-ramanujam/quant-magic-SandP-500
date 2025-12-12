import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react";
import { describe, it, beforeEach, vi, expect } from "vitest";
import App from "./App";
import { sampleResponses } from "./fixtures/queryResponses";
import { normalizeResponse, runQuery, fetchHealth } from "./api/client";

vi.mock("./api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/client")>();
  return {
    ...actual,
    fetchHealth: vi.fn(),
    runQuery: vi.fn(),
  };
});

const mockedRunQuery = vi.mocked(runQuery);
const mockedFetchHealth = vi.mocked(fetchHealth);

const submitQuestion = async (question: string) => {
  const input = screen.getByPlaceholderText(/type your message here/i);
  await act(async () => {
    await userEvent.clear(input);
    await userEvent.type(input, question);
    const form = input.closest("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);
  });
};

describe("App", () => {
  beforeEach(() => {
    mockedFetchHealth.mockResolvedValue({
      status: "ok",
      llm_available: true,
      message: "LLM available",
    });
    mockedRunQuery.mockReset();
  });

  it("renders formatted responses with table, reasoning, and request id", async () => {
    mockedRunQuery.mockResolvedValueOnce(
      normalizeResponse(sampleResponses.timeSeries),
    );

    await act(async () => {
      render(<App />);
    });
    await submitQuestion("Show Apple's revenue over FY2021-2023");

    await screen.findByText(/Business Summary & Key Findings/i);
    expect(
      screen.getByText(/Apple’s revenue expanded over FY2021–FY2023/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/FY2022 revenue: \$394.3B/i)).toBeInTheDocument();
    expect(screen.getByText(/Top rows/i)).toBeInTheDocument();

    const toggle = await screen.findByRole("button", {
      name: /Reasoning & SQL/i,
    });
    await userEvent.click(toggle);

    expect(
      screen.getByText(sampleResponses.timeSeries.sql as string),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/template `time_series_revenue` · 3 rows/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Request ID: req-ts-001/i)).toBeInTheDocument();
  });

  it("handles missing SQL gracefully and surfaces truncation notes", async () => {
    const noSql = normalizeResponse({ ...sampleResponses.medium, sql: "" });
    mockedRunQuery.mockResolvedValueOnce(noSql);

    await act(async () => {
      render(<App />);
    });
    await submitQuestion("Show top growth and profitability leaders");

    await screen.findByText(/Business Summary & Key Findings/i);
    expect(
      screen.getByText(/Table truncated to top 5 rows./i),
    ).toBeInTheDocument();

    const toggle = await screen.findByRole("button", {
      name: /Reasoning & SQL/i,
    });
    await userEvent.click(toggle);

    expect(
      screen.getByText(/SQL not returned for this answer/i),
    ).toBeInTheDocument();
  });

  it("shows degraded health badge when LLM is unavailable", async () => {
    mockedFetchHealth.mockResolvedValueOnce({
      status: "degraded",
      llm_available: false,
      message: "LLM unavailable",
    });
    mockedRunQuery.mockResolvedValueOnce(
      normalizeResponse(sampleResponses.simple),
    );

    await act(async () => {
      render(<App />);
    });
    await screen.findByText(/LLM degraded/i);

    await submitQuestion("How many companies are in Technology?");
    await waitFor(() =>
      expect(mockedRunQuery).toHaveBeenCalledWith(
        expect.objectContaining({ question: expect.any(String) }),
      ),
    );
  });

  it("surfaces guided starters and routes them to runQuery", async () => {
    mockedRunQuery.mockResolvedValue(normalizeResponse(sampleResponses.simple));

    await act(async () => {
      render(<App />);
    });

    const techButton = await screen.findByRole("button", { name: /Technology/i });
    await userEvent.click(techButton);

    const starterText =
      "Which Technology companies lead revenue growth since 2020?";
    const starterButton = await screen.findByRole("button", {
      name: starterText,
    });
    await userEvent.click(starterButton);

    await waitFor(() =>
      expect(mockedRunQuery).toHaveBeenCalledWith(
        expect.objectContaining({ question: starterText }),
      ),
    );
  });
});
