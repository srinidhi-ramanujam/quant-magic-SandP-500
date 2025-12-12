import type {
  ApiErrorResponse,
  ConversationTurnPayload,
  HealthResponse,
  NormalizedAnswer,
  PresentationPayload,
  PresentationTable,
  QueryError,
  QueryResponse,
  ReasoningTrace,
} from "../types";

export type StreamEvent = {
  event: string;
  data: Record<string, unknown>;
};

const asArray = <T>(value: unknown, fallback: T[] = []): T[] => {
  if (Array.isArray(value)) return value as T[];
  return fallback;
};

const normalizeTable = (table?: PresentationTable | null): PresentationTable | null => {
  if (!table) return null;
  const rows = asArray<Record<string, unknown>>(table.rows, []);
  const providedColumns = asArray<string>(table.columns, []);
  const columns =
    providedColumns.length > 0
      ? providedColumns
      : rows.length > 0
        ? Object.keys(rows[0])
        : [];

  return {
    columns,
    rows,
    truncated: Boolean(table.truncated),
  };
};

const normalizePresentation = (
  presentation?: PresentationPayload | null,
): PresentationPayload | null => {
  if (!presentation) return null;
  return {
    narrative: presentation.narrative,
    highlights: asArray<string>(presentation.highlights, []),
    table: normalizeTable(presentation.table ?? null),
    warnings: asArray<string>(presentation.warnings, []),
  };
};

export class QueryClientError extends Error implements QueryError {
  requestId?: string;

  constructor(message: string, requestId?: string) {
    super(message);
    this.name = "QueryClientError";
    this.requestId = requestId;
  }
}

export const normalizeResponse = (response: QueryResponse): NormalizedAnswer => {
  const metadata = response.metadata ?? {};
  const requestId =
    typeof metadata.request_id === "string" ? (metadata.request_id as string) : undefined;
  const totalTimeSeconds =
    typeof metadata.total_time_seconds === "number"
      ? (metadata.total_time_seconds as number)
      : undefined;
  const rowCount =
    typeof metadata.row_count === "number" ? (metadata.row_count as number) : undefined;

  const presentation = normalizePresentation(response.presentation ?? null);
  const reasoning: ReasoningTrace | null = response.reasoning_trace ?? null;

  const sqlRaw = response.sql ?? null;
  const sql =
    typeof sqlRaw === "string" && sqlRaw.trim().length > 0 ? sqlRaw.trim() : null;

  const narrative = presentation?.narrative ?? response.answer ?? "";

  return {
    answer: response.answer ?? "",
    narrative,
    highlights: presentation?.highlights ?? [],
    table: presentation?.table ?? null,
    warnings: presentation?.warnings ?? [],
    reasoning,
    sql,
    sqlHint: response.sql_collapsible_hint ?? reasoning?.summary ?? null,
    success: Boolean(response.success),
    error: response.error ?? null,
    requestId,
    totalTimeSeconds,
    rowCount,
    rawMetadata: metadata,
  };
};

export const fetchHealth = async (): Promise<HealthResponse | null> => {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) return null;
    const json = (await response.json()) as HealthResponse;
    return json;
  } catch {
    return null;
  }
};

type QueryParams = {
  question: string;
  history?: ConversationTurnPayload[];
  include_formatted_answer?: boolean;
  debug_mode?: boolean;
};

type StreamParams = QueryParams & {
  onEvent?: (event: StreamEvent) => void;
};

export const runQuery = async ({
  question,
  history = [],
  include_formatted_answer = true,
  debug_mode = false,
}: QueryParams): Promise<NormalizedAnswer> => {
  const payload = {
    question,
    history,
    include_formatted_answer,
    debug_mode,
  };

  let response: Response;
  try {
    response = await fetch("/api/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new QueryClientError(
      error instanceof Error
        ? error.message
        : "Unable to reach the API. Please confirm the backend is running.",
    );
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorPayload = (await response.json()) as ApiErrorResponse;
      detail = errorPayload?.detail;
    } catch {
      detail = undefined;
    }
    const message =
      detail ||
      `API error (${response.status} ${response.statusText || "Unknown error"})`;
    throw new QueryClientError(message);
  }

  const json = (await response.json()) as QueryResponse;
  return normalizeResponse(json);
};

const parseSseStream = (
  chunk: string,
  onEvent: (event: StreamEvent) => void,
  bufferRef: { current: string },
) => {
  const combined = bufferRef.current + chunk;
  const parts = combined.split("\n\n");
  bufferRef.current = parts.pop() || "";

  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const lines = trimmed.split("\n");
    let eventType: string | null = null;
    let dataLine: string | null = null;

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventType = line.replace("event:", "").trim();
      } else if (line.startsWith("data:")) {
        dataLine = line.replace("data:", "").trim();
      }
    }

    if (!eventType || !dataLine) continue;

    try {
      const data = JSON.parse(dataLine) as Record<string, unknown>;
      onEvent({ event: eventType, data });
    } catch (error) {
      console.warn("[ui] failed to parse SSE event", { error, part });
    }
  }
};

export const runQueryStream = async ({
  question,
  history = [],
  include_formatted_answer = true,
  debug_mode = false,
  onEvent,
}: StreamParams): Promise<NormalizedAnswer> => {
  const payload = {
    question,
    history,
    include_formatted_answer,
    debug_mode,
  };

  let response: Response;
  try {
    response = await fetch("/api/query/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (error) {
    throw new QueryClientError(
      error instanceof Error
        ? error.message
        : "Unable to reach the API. Please confirm the backend is running.",
    );
  }

  if (!response.ok || !response.body) {
    throw new QueryClientError(
      `API error (${response.status} ${response.statusText || "Unknown error"})`,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const bufferRef = { current: "" };

  let finalPayload: QueryResponse | null = null;
  let streamError: string | null = null;

  const handleEvent = (event: StreamEvent) => {
    if (onEvent) onEvent(event);
    if (event.event === "final") {
      finalPayload = event.data as unknown as QueryResponse;
    }
    if (event.event === "error" && typeof event.data?.error === "string") {
      streamError = event.data.error;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    parseSseStream(text, handleEvent, bufferRef);
  }

  // Flush any trailing buffered event
  if (bufferRef.current.trim().length > 0) {
    parseSseStream("", handleEvent, bufferRef);
  }

  if (streamError) {
    throw new QueryClientError(streamError);
  }

  if (!finalPayload) {
    throw new QueryClientError("Stream ended without a final payload.");
  }

  return normalizeResponse(finalPayload);
};
