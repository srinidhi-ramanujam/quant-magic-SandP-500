export type PresentationTable = {
  columns: string[];
  rows: Record<string, unknown>[];
  truncated?: boolean;
};

export type PresentationPayload = {
  narrative: string;
  highlights?: string[];
  table?: PresentationTable | null;
  warnings?: string[];
};

export type ReasoningTrace = {
  template_id?: string | null;
  generation_method?: string | null;
  row_count?: number | null;
  elapsed_seconds?: number | null;
  summary?: string | null;
  warnings?: string[];
};

export type ConversationTurnPayload = {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
};

export type QueryResponse = {
  answer: string;
  success: boolean;
  sql?: string | null;
  metadata?: Record<string, unknown>;
  sources?: string[] | null;
  debug?: Record<string, unknown> | null;
  error?: string | null;
  presentation?: PresentationPayload | null;
  reasoning_trace?: ReasoningTrace | null;
  sql_collapsible_hint?: string | null;
};

export type HealthResponse = {
  status: string;
  llm_available: boolean;
  message: string;
};

export type NormalizedAnswer = {
  answer: string;
  narrative: string;
  highlights: string[];
  table: PresentationTable | null;
  warnings: string[];
  reasoning: ReasoningTrace | null;
  sql: string | null;
  sqlHint: string | null;
  success: boolean;
  error: string | null;
  requestId?: string;
  totalTimeSeconds?: number;
  rowCount?: number;
  rawMetadata: Record<string, unknown>;
};

export type QueryError = {
  message: string;
  requestId?: string;
};

export type ApiErrorResponse = {
  detail?: string;
};
