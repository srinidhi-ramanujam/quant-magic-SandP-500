import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import {
  fetchHealth,
  QueryClientError,
  runQuery,
  runQueryStream,
  type StreamEvent,
} from "./api/client";
import type {
  ConversationTurnPayload,
  NormalizedAnswer,
  PresentationPayload,
  ReasoningTrace,
} from "./types";
import { TOP_SECTORS, type Sector } from "./fixtures/sectors";
import { FEATURED_COMPANIES, type FeaturedCompany } from "./fixtures/companies";

const README_URL =
  "https://github.com/srinidhi-ramanujam/quant-magic-SandP-500/blob/master/README.md";
const DATA_SECTION_URL = `${README_URL}#data-layer`;
const OVERVIEW_SECTIONS = [
  {
    title: "What we built",
    items: [
      "NL → SQL copilot for the S&P 500 that routes, generates, validates, and executes queries on DuckDB.",
      "FastAPI backend mirrors CLI behavior; React + Tailwind UI adds chat, health, and reasoning panels.",
    ],
  },
  {
    title: "Why it matters",
    items: [
      "Cuts time-to-insight for sector and company analysis without spreadsheet spelunking.",
      "Keeps answers repeatable with telemetry, SQL transparency, and validation before execution.",
    ],
  },
  {
    title: "How it works",
    items: [
      "Hybrid pipeline: deterministic entity extraction and template routing with LLM confirmation/fallback.",
      "Two-pass validation (syntax + semantic) plus formatter for narratives, highlights, tables, and warnings.",
      "DuckDB over 15.5M facts (589 companies) powered by read-only Parquet catalogs and template intelligence.",
    ],
  },
  {
    title: "Data footprint",
    items: [
      "`data/parquet/num.parquet` for facts, `companies_with_sectors.parquet` for entities, `query_intelligence.parquet` for template metadata.",
      "Shared QueryEngine + ResponseFormatter serve both CLI and API so UI stays in sync with backend logic.",
    ],
  },
];
const DOCS_SECTIONS = [
  {
    title: "What it is",
    items: [
      "An S&P 500 copilot: ask plain-English questions, get answers with the exact SQL and data that back them.",
      "Built for analysts: sector trends, company deep-dives, ratios, and time-series insights without wrangling spreadsheets.",
      "Transparent by design: every answer shows its reasoning and the SQL it ran—no black boxes.",
    ],
  },
  {
    title: "Setup & commands",
    items: [
      "Backend: source .venv/bin/activate; python -m src.api.app via uvicorn or run_local_ui.sh",
      "Frontend: from frontend/, npm install (first time) then npm run dev -- --host --port 5173",
      "CLI: python -m src.cli \"<question>\" --debug for parity with API/UI",
    ],
  },
  {
    title: "How it works (innovations)",
    items: [
      "Hybrid routing: deterministic entity/template matching first, LLM only when needed—fast and predictable.",
      "Two-pass guardrails: syntax + semantic SQL checks before running, plus formatted narratives and tables after.",
      "Full traceability: live reasoning feed, SQL previews, row counts, and template IDs streamed into the UI.",
      "Resilient UX: streaming progress, heartbeats, and cached context so slow answers still feel alive.",
    ],
  },
  {
    title: "Testing & quality",
    items: [
      "python -m pytest -m \"not integration\" for fast checks; full suite under tests/",
      "Formatting: python -m black src/ tests/",
      "Health: /api/health and UI badge show API + LLM availability",
    ],
  },
  {
    title: "Data & responsible use",
    items: [
      "Read-only Parquet catalogs; DuckDB executes SQL locally—no writes",
      "Azure OpenAI responses API; keep keys in env vars, never in the client",
      "Explainability: SQL and reasoning trace are exposed for every answer",
    ],
  },
];

const SCHEMA_SECTIONS = [
  {
    title: "Data layout",
    items: [
      "Parquet catalogs in data/parquet/ mounted by DuckDB; no runtime mutation",
      "num.parquet: 15.5M financial facts; companies_with_sectors.parquet: 589 entities",
      "query_intelligence.parquet: template metadata; financial_concepts/ratios define mappings",
    ],
  },
  {
    title: "Core tables/views",
    items: [
      "Facts: fiscal_year, fiscal_period, company, metric, value",
      "Entities: company name, ticker, sector; aliases for lookup",
      "Template metadata: template_id, category, parameters, SQL skeleton",
    ],
  },
  {
    title: "Query pipeline hooks",
    items: [
      "Entity extractor resolves companies/sectors/metrics then slots parameters",
      "SQL generator picks a template, fills parameters, returns SQL + template id",
      "Response formatter shapes tables + narrative; UI shows row counts and SQL",
    ],
  },
  {
    title: "Access patterns",
    items: [
      "Read-only scans via DuckDB; filters by sector/year/metric per template",
      "Reasoning trace exposes template, row counts, and the executed SQL",
      "Use CLI/API/UI to run queries; no direct writes to parquet files",
    ],
  },
];

type MessageMetadata = {
  requestId?: string;
  sql?: string | null;
  totalTimeSeconds?: number;
  rowCount?: number;
  presentation?: PresentationPayload | null;
  reasoningTrace?: ReasoningTrace | null;
  sqlHint?: string | null;
  warnings?: string[];
  rawMetadata?: Record<string, unknown>;
  success?: boolean;
  error?: string | null;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  status?: "loading" | "done" | "error";
  metadata?: MessageMetadata;
};

type ChatSession = {
  id: string;
  title: string;
  timestamp: string;
  messages?: Message[];
};

type HealthState = {
  status: "checking" | "ok" | "degraded" | "offline";
  message?: string;
  llmAvailable?: boolean;
};

const logInfo = (label: string, payload: unknown) => {
  console.info(`[ui] ${label}`, payload);
};

const buildHistoryPayload = (
  thread: Message[],
  limit = 6,
): ConversationTurnPayload[] => {
  if (!thread.length) return [];
  const recent = thread.slice(-limit);
  return recent.map((message) => ({
    role: message.role,
    content: message.content,
    timestamp: message.timestamp,
  }));
};

const toPresentation = (answer: NormalizedAnswer): PresentationPayload => ({
  narrative: answer.narrative || answer.answer,
  highlights: answer.highlights,
  table: answer.table,
  warnings: answer.warnings,
});

const toMessageMetadata = (answer: NormalizedAnswer): MessageMetadata => ({
  requestId: answer.requestId,
  sql: answer.sql,
  totalTimeSeconds: answer.totalTimeSeconds,
  rowCount: answer.rowCount,
  presentation: toPresentation(answer),
  reasoningTrace: answer.reasoning,
  sqlHint: answer.sqlHint,
  warnings: answer.warnings,
  rawMetadata: answer.rawMetadata,
  success: answer.success,
  error: answer.error,
});

const buildSectorStarters = (sector: Sector): string[] => {
  const label = sector.label;
  return [
    `Which ${label} companies lead revenue growth since 2020?`,
    `How have operating margins trended for ${label} over the last 4 years?`,
    `Top ${label} companies by free cash flow and margin stability since 2020?`,
    `Which ${label} firms improved ROIC the most over the past 3 years?`,
    `Who gained share in ${label} based on revenue CAGR and margins?`,
  ];
};

const buildCompanyStarters = (company: FeaturedCompany): string[] => {
  const name = company.name;
  return [
    `Show revenue and operating margin trends for ${name} since 2020.`,
    `How stable is free cash flow for ${name} over the last 4 fiscal years?`,
    `Compare ${name}'s margins vs peers in its sector for the last 3 years.`,
    `Which segments drive growth for ${name} since 2020?`,
    `How did ${name}'s leverage and cash balance change over the last 4 years?`,
  ];
};

function App() {
  const [question, setQuestion] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<HealthState>({ status: "checking" });
  const [chatHistory, setChatHistory] = useState<ChatSession[]>([]);
  const [sqlPanelOpen, setSqlPanelOpen] = useState<Record<string, boolean>>({});
  const [selectedSector, setSelectedSector] = useState<Sector | null>(null);
  const [selectedCompany, setSelectedCompany] = useState<FeaturedCompany | null>(null);
  const [companySearch, setCompanySearch] = useState("");
  const [starterQuestions, setStarterQuestions] = useState<string[]>([]);
  const [showOverview, setShowOverview] = useState(false);
  const [showDocs, setShowDocs] = useState(false);
  const [showSchema, setShowSchema] = useState(false);
  const [showSessionHistory, setShowSessionHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scriptedTimerRef = useRef<number | null>(null);
  const heartbeatTimerRef = useRef<number | null>(null);
  const slowStartTimeoutRef = useRef<number | null>(null);
  const slowIntervalRef = useRef<number | null>(null);
  const latestContextRef = useRef<{
    companies: string[];
    sectors: string[];
    metrics: string[];
    templateId: string | null;
    generationMethod: string | null;
    parameters: Record<string, unknown> | null;
    sqlPreview: string | null;
  }>({
    companies: [],
    sectors: [],
    metrics: [],
    templateId: null,
    generationMethod: null,
    parameters: null,
    sqlPreview: null,
  });

  useEffect(() => {
    let active = true;
    const checkConnection = async () => {
      const result = await fetchHealth();
      if (!active) return;
      if (!result) {
        setHealth({ status: "offline", message: "API unreachable" });
      } else {
        setHealth({
          status: result.status === "ok" ? "ok" : "degraded",
          llmAvailable: result.llm_available,
          message: result.message,
        });
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (selectedSector) {
      setStarterQuestions(buildSectorStarters(selectedSector));
      return;
    }
    if (selectedCompany) {
      setStarterQuestions(buildCompanyStarters(selectedCompany));
      return;
    }
    setStarterQuestions([]);
  }, [selectedSector, selectedCompany]);

  const toggleSqlPanel = (id: string) => {
    setSqlPanelOpen((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const inferContextSummary = (text: string) => {
    const yearMatch = text.match(/20\d{2}/);
    const year = yearMatch ? yearMatch[0] : null;
    const sector =
      selectedSector?.label ||
      (text.toLowerCase().includes("technology") ? "Technology" : null);
    const company =
      selectedCompany?.name ||
      FEATURED_COMPANIES.find((c) =>
        text.toLowerCase().includes(c.name.toLowerCase()),
      )?.name ||
      null;
    const metricMatch = text.match(
      /(revenue|margin|ebitda|cash flow|free cash flow|roe|debt|leverage|turnover)/i,
    );
    const metric = metricMatch ? metricMatch[0] : null;

    const subject = company || sector || "this query";
    const kpi = metric ? `the ${metric}` : "key metrics";
    const yearLabel = year ? ` for ${year}` : "";

    return `User is asking about ${subject} focusing on ${kpi}${yearLabel}. I’ll break this down, confirm intent, choose a template, run SQL, and then format the answer.`;
  };

  const sendQuestion = async (
    questionText: string,
    source: "user" | "starter" = "user",
    options?: { keepInput?: boolean },
  ) => {
    const trimmedQuestion = questionText.trim();
    if (!trimmedQuestion || loading) return;
    const shouldKeepInput = options?.keepInput ?? false;

    const historyPayload = buildHistoryPayload(messages);
    const isFirstMessage = messages.length === 0;
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: trimmedQuestion,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };
    const assistantId = (Date.now() + 1).toString();
    const initialThinking = inferContextSummary(trimmedQuestion);
    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: source === "starter" ? initialThinking : initialThinking,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      status: "loading",
    };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setQuestion(shouldKeepInput ? questionText : "");
    setLoading(true);
    logInfo("question", {
      id: userMessage.id,
      question: trimmedQuestion,
      source,
    });

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    const applyAnswer = (answer: NormalizedAnswer) => {
      const metadata = toMessageMetadata(answer);
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: answer.narrative || answer.answer || "No answer returned.",
                status: answer.success ? "done" : "error",
                metadata,
              }
            : message,
        ),
      );

      if (isFirstMessage) {
        const assistantFinal: Message = {
          ...assistantMessage,
          content: answer.narrative || answer.answer || "No answer returned.",
          status: answer.success ? "done" : "error",
          metadata,
        };
        const snapshot = [userMessage, assistantFinal];
        const newSession: ChatSession = {
          id: Date.now().toString(),
          title: userMessage.content.slice(0, 50) + "...",
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
          messages: snapshot,
        };
        setChatHistory((prev) => [newSession, ...prev]);
      }

      logInfo("response", {
        id: assistantId,
        requestId: metadata.requestId,
        success: metadata.success,
        sql: metadata.sql,
      });
    };

    const progressLines: string[] = [initialThinking];
    const updateQueue: string[] = [];
    let flushing = false;
    const timeouts: number[] = [];

    const scriptedSteps = [
      "Interpreting the question and confirming entities and metrics…",
      "Checking which template or SQL path best fits…",
      "Drafting the SQL and validating parameters…",
      "Running the SQL in DuckDB and checking result quality…",
      "Shaping a polished answer with highlights and tables…",
    ];

    const enqueueUpdate = (content: string) => {
      updateQueue.push(content);
      if (!flushing) flushQueue();
    };

    const flushQueue = () => {
      if (updateQueue.length === 0) {
        flushing = false;
        return;
      }
      flushing = true;
      const next = updateQueue.shift();
      const delay = 550 + Math.floor(Math.random() * 650);
      const timeoutId = window.setTimeout(() => {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, content: next ?? "", status: "loading" } : message,
          ),
        );
        flushQueue();
      }, delay);
      timeouts.push(timeoutId);
    };

    const startScriptedPacer = () => {
      let stepIndex = 0;
      scriptedTimerRef.current = window.setInterval(() => {
        if (stepIndex >= scriptedSteps.length) return;
        progressLines.push(scriptedSteps[stepIndex]);
        enqueueUpdate(progressLines.join("\n\n"));
        stepIndex += 1;
      }, 900);
    };

    const startHeartbeat = () => {
      heartbeatTimerRef.current = window.setInterval(() => {
        enqueueUpdate(progressLines.join("\n\n") + "\n•");
      }, 700);
    };

    const stopScriptedPacer = () => {
      if (scriptedTimerRef.current) {
        window.clearInterval(scriptedTimerRef.current);
        scriptedTimerRef.current = null;
      }
    };

    const stopHeartbeat = () => {
      if (heartbeatTimerRef.current) {
        window.clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    };

    const clearPendingTimers = () => {
      timeouts.forEach((id) => window.clearTimeout(id));
      stopScriptedPacer();
      stopHeartbeat();
      if (slowStartTimeoutRef.current) {
        window.clearTimeout(slowStartTimeoutRef.current);
        slowStartTimeoutRef.current = null;
      }
      if (slowIntervalRef.current) {
        window.clearInterval(slowIntervalRef.current);
        slowIntervalRef.current = null;
      }
    };

    // kick off scripted pacing immediately so something appears within 1s
    startScriptedPacer();
    startHeartbeat();
    slowStartTimeoutRef.current = window.setTimeout(() => {
      slowIntervalRef.current = window.setInterval(() => {
        const ctx = latestContextRef.current;
        const pieces = [];
        if (ctx.companies.length) pieces.push(`Companies: ${ctx.companies.join(", ")}`);
        if (ctx.sectors.length) pieces.push(`Sectors: ${ctx.sectors.join(", ")}`);
        if (ctx.metrics.length) pieces.push(`Metrics: ${ctx.metrics.join(", ")}`);
        if (ctx.templateId || ctx.generationMethod) {
          pieces.push(
            `Template: ${ctx.templateId || "TBD"} (${ctx.generationMethod || "hybrid"})`,
          );
        }
        if (ctx.parameters && Object.keys(ctx.parameters).length) {
          pieces.push(
            `Params: ${Object.entries(ctx.parameters)
              .map(([k, v]) => `${k}=${v}`)
              .join(", ")}`,
          );
        }
        if (ctx.sqlPreview) {
          pieces.push(`SQL draft: ${ctx.sqlPreview.slice(0, 120)}…`);
        }
        const filler =
          pieces.length > 0
            ? `Still working—${pieces.join(" · ")}`
            : "Still working—validating results and formatting…";
        enqueueUpdate(progressLines.join("\n\n") + "\n" + filler);
      }, 4500);
    }, 7000);

    const handleStreamEvent = (event: StreamEvent) => {
      if (event.event === "start") {
        progressLines.push("Starting the analysis…");
        enqueueUpdate(progressLines.join("\n\n"));
        return;
      }

      if (event.event === "reasoning") {
        const summary = typeof event.data?.summary === "string" ? event.data.summary : null;
        const stage = typeof event.data?.stage === "string" ? event.data.stage : "";
        const companies = Array.isArray(event.data?.companies)
          ? (event.data.companies as string[]).filter(Boolean)
          : [];
        const sectors = Array.isArray(event.data?.sectors)
          ? (event.data.sectors as string[]).filter(Boolean)
          : [];
        const metrics = Array.isArray(event.data?.metrics)
          ? (event.data.metrics as string[]).filter(Boolean)
          : [];
        const templateId =
          typeof event.data?.template_id === "string" ? (event.data.template_id as string) : null;
        const generationMethod =
          typeof event.data?.generation_method === "string"
            ? (event.data.generation_method as string)
            : null;
        const sqlPreview =
          typeof event.data?.sql_preview === "string" ? (event.data.sql_preview as string) : null;
        const parameters =
          event.data?.parameters && typeof event.data.parameters === "object"
            ? (event.data.parameters as Record<string, unknown>)
            : null;

        if (stage === "context_summary") {
          const pieces = [];
          if (companies.length) pieces.push(`Companies: ${companies.join(", ")}`);
          if (sectors.length) pieces.push(`Sectors: ${sectors.join(", ")}`);
          if (metrics.length) pieces.push(`Metrics: ${metrics.join(", ")}`);
          latestContextRef.current.companies = companies;
          latestContextRef.current.sectors = sectors;
          latestContextRef.current.metrics = metrics;
          if (pieces.length) {
            progressLines.push(`Context locked in. ${pieces.join(" · ")}`);
            enqueueUpdate(progressLines.join("\n\n"));
            return;
          }
        }

        if (stage === "template_selection") {
          const bits = [];
          if (templateId) bits.push(`Template: ${templateId}`);
          if (generationMethod) bits.push(`Method: ${generationMethod}`);
          if (parameters && Object.keys(parameters).length > 0) {
            bits.push(`Parameters: ${Object.entries(parameters).map(([k, v]) => `${k}=${v}`).join(", ")}`);
          }
          if (sqlPreview) {
            bits.push(`SQL draft: ${sqlPreview.slice(0, 160)}…`);
          }
          latestContextRef.current.templateId = templateId;
          latestContextRef.current.generationMethod = generationMethod;
          latestContextRef.current.parameters = parameters;
          latestContextRef.current.sqlPreview = sqlPreview;
          progressLines.push(bits.join(" · ") || "Template chosen, drafting SQL…");
          enqueueUpdate(progressLines.join("\n\n"));
          return;
        }

        if (stage === "execution") {
          const rows =
            typeof event.data?.row_count === "number" ? ` Rows: ${event.data.row_count}.` : "";
          progressLines.push(`Executing query on DuckDB.${rows}`);
          enqueueUpdate(progressLines.join("\n\n"));
          return;
        }

        if (stage === "formatting_start") {
          progressLines.push("Formatting the answer with narrative, highlights, and tables…");
          enqueueUpdate(progressLines.join("\n\n"));
          return;
        }

        if (summary) {
          progressLines.push(summary);
          enqueueUpdate(progressLines.join("\n\n"));
        }
        return;
      }

      if (event.event === "execution") {
        const rows =
          typeof event.data?.row_count === "number" ? ` (${event.data.row_count} rows)` : "";
        progressLines.push(`Running SQL and fetching data${rows}…`);
        enqueueUpdate(progressLines.join("\n\n"));
        return;
      }

      if (event.event === "answer_formatter") {
        progressLines.push("Polishing the narrative and highlights…");
        enqueueUpdate(progressLines.join("\n\n"));
      }

      if (event.event === "heartbeat") {
        enqueueUpdate(progressLines.join("\n\n") + "\n•");
      }
    };

    const applyError = (messageText: string, requestId?: string) => {
      setMessages((prev) =>
        prev.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                content: messageText,
                status: "error",
                metadata: {
                  ...message.metadata,
                  error: messageText,
                  requestId,
                  success: false,
                },
              }
            : message,
        ),
      );
    };

    try {
      let answer: NormalizedAnswer | null = null;
      try {
        answer = await runQueryStream({
          question: trimmedQuestion,
          history: historyPayload,
          include_formatted_answer: true,
          onEvent: handleStreamEvent,
        });
      } catch (streamError) {
        console.warn("[ui] streaming failed, falling back to non-streaming", streamError);
        answer = await runQuery({
          question: trimmedQuestion,
          history: historyPayload,
          include_formatted_answer: true,
        });
      }
      applyAnswer(answer);
      clearPendingTimers();
    } catch (error) {
      clearPendingTimers();
      if (error instanceof QueryClientError) {
        applyError(error.message, error.requestId);
      } else if (error instanceof Error) {
        applyError(error.message);
      } else {
        applyError("Unexpected error while calling the API.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!question.trim() || loading) return;
    await sendQuestion(question, "user");
  };

  const handleTextareaChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setQuestion(event.target.value);
    // Auto-resize textarea
    event.target.style.height = "auto";
    event.target.style.height = event.target.scrollHeight + "px";
  };

  const handleSelectSector = (sector: Sector) => {
    setSelectedSector(sector);
    setSelectedCompany(null);
    setCompanySearch("");
  };

  const handleSelectCompany = (company: FeaturedCompany) => {
    setSelectedCompany(company);
    setSelectedSector(null);
  };

  const handleStarterClick = async (starter: string) => {
    setQuestion(starter);
    setStarterQuestions([]);
    setSelectedSector(null);
    setSelectedCompany(null);
    await sendQuestion(starter, "starter", { keepInput: true });
  };

  const handleNewChat = () => {
    addConversationSummary();
    setMessages([]);
    setQuestion("");
    setStarterQuestions([]);
    setSelectedSector(null);
    setSelectedCompany(null);
    setCompanySearch("");
  };

  const filteredCompanies =
    companySearch.trim().length === 0
      ? FEATURED_COMPANIES
      : FEATURED_COMPANIES.filter((company) =>
          company.name.toLowerCase().includes(companySearch.toLowerCase()) ||
          (company.ticker || "").toLowerCase().includes(companySearch.toLowerCase()),
        );

  const addConversationSummary = () => {
    if (!messages.length) return;
    const snapshot = messages.map((m) => ({
      ...m,
      metadata: m.metadata ? { ...m.metadata } : undefined,
    }));
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
    const summaryParts = [];
    if (lastUser) summaryParts.push(lastUser.content.slice(0, 80));
    if (lastAssistant) summaryParts.push(lastAssistant.content.slice(0, 80));
    const summary = summaryParts.join(" • ");
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: summary || "Previous conversation",
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      messages: snapshot,
    };
    setChatHistory((prev) => [newSession, ...prev]);
  };

  const selectedContextLabel =
    selectedSector?.label ||
    (selectedCompany ? `${selectedCompany.name}${selectedCompany.ticker ? ` (${selectedCompany.ticker})` : ""}` : null);

  const healthLabel =
    health.status === "ok"
      ? "API & LLM available"
      : health.status === "degraded"
        ? "LLM degraded"
        : health.status === "offline"
          ? "API unreachable"
          : "Checking API";
  const healthBadgeClass =
    health.status === "ok"
      ? "bg-emerald-500/20 text-emerald-300"
      : health.status === "degraded"
        ? "bg-amber-500/20 text-amber-200"
        : health.status === "offline"
          ? "bg-red-500/20 text-red-300"
          : "bg-slate-700/40 text-slate-300";
  const healthDotClass =
    health.status === "ok"
      ? "bg-emerald-400"
      : health.status === "degraded"
        ? "bg-amber-400"
        : health.status === "offline"
          ? "bg-red-400"
          : "bg-slate-400";

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-slate-100 overflow-hidden">
      {/* Left Sidebar */}
      <div className="w-80 bg-[#111111] border-r border-slate-800 flex flex-col overflow-y-auto">
        {/* Brand */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-brand-dark to-brand rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xl">A</span>
            </div>
            <span className="text-xl font-semibold text-white">
              ASCENDION
            </span>
          </div>
        </div>

        {/* New Chat + Session History */}
        <div className="p-4 space-y-3 relative">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-brand-dark to-brand hover:from-brand hover:to-brand-light text-white rounded-lg font-medium transition-all"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            New Chat
          </button>
          <div className="relative">
            <button
              onClick={() => setShowSessionHistory((prev) => !prev)}
              className="w-full flex items-center justify-between text-slate-300 text-sm px-3 py-2 rounded-lg hover:bg-slate-800/60 transition-colors border border-slate-800"
              aria-expanded={showSessionHistory}
            >
              <span className="flex items-center gap-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                Conversation History
              </span>
              <svg
                className={`w-4 h-4 transition-transform ${showSessionHistory ? "rotate-90" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
            {showSessionHistory && (
              <div className="absolute top-full left-0 right-0 mt-2 z-20 bg-[#0f172a] border border-slate-800 rounded-xl shadow-2xl max-h-64 overflow-y-auto">
                <div className="p-3 space-y-2">
                  {chatHistory.length === 0 && (
                    <div className="text-xs text-slate-500 px-1 py-2">
                      No prior conversations yet. Ask a question, then start a new chat to save it here.
                    </div>
                  )}
                  {chatHistory.map((chat) => (
                    <button
                      key={chat.id}
                      onClick={() => {
                        if (chat.messages && chat.messages.length) {
                          setMessages(chat.messages);
                          setShowSessionHistory(false);
                        }
                      }}
                      className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-800 text-sm text-slate-200 hover:border-slate-600 transition-colors"
                    >
                      <div className="truncate font-medium">{chat.title}</div>
                      <div className="text-xs text-slate-500">{chat.timestamp}</div>
                      {!chat.messages?.length && (
                        <div className="text-[11px] text-amber-300 mt-1">
                          Saved before transcript capture; cannot reload.
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Spacer to push rest down if needed */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 py-2" />
        </div>

        {/* Guided Explorer */}
        <div className="border-t border-slate-800 p-4 space-y-4">
          <div className="flex items-center gap-2 text-slate-300 text-sm font-medium">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6v6l4 2"
              />
            </svg>
            Guided Explorer
          </div>

          {/* Sector selector */}
          <div className="space-y-2">
            <div className="text-xs uppercase tracking-wide text-slate-500">
              Sectors
            </div>
            <div className="flex flex-wrap gap-2">
              {TOP_SECTORS.map((sector) => {
                const isActive = selectedSector?.id === sector.id;
                return (
                  <button
                    key={sector.id}
                    onClick={() => handleSelectSector(sector)}
                    className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                      isActive
                        ? "border-brand bg-brand/20 text-white"
                        : "border-slate-700 text-slate-200 hover:border-slate-500"
                    }`}
                  >
                    {sector.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Company selector */}
          <div className="space-y-3">
            <div className="text-xs uppercase tracking-wide text-slate-500">
              Company Deep-dives
            </div>
            <div className="relative">
              <input
                value={companySearch}
                onChange={(e) => setCompanySearch(e.target.value)}
                placeholder="Search top companies (e.g., Apple, NVDA)"
                className="w-full bg-[#1e293b] border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent"
              />
            </div>
            <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
              {filteredCompanies.map((company) => {
                const isActive = selectedCompany?.name === company.name;
                return (
                  <button
                    key={company.name}
                    onClick={() => handleSelectCompany(company)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center justify-between transition-colors ${
                      isActive
                        ? "bg-brand/20 text-white border border-brand"
                        : "bg-slate-800/40 text-slate-200 hover:bg-slate-800/70"
                    }`}
                  >
                    <span>{company.name}</span>
                    {company.ticker && (
                      <span className="text-xs text-slate-400">{company.ticker}</span>
                    )}
                  </button>
                );
              })}
              {filteredCompanies.length === 0 && (
                <div className="text-xs text-slate-500 px-1">
                  No matches. Try another name or ticker.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Quick Access */}
        <div className="border-t border-slate-800 p-4">
          <div className="flex items-center gap-2 text-slate-400 text-sm mb-3">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
            Quick Access
          </div>
          <div className="space-y-1">
            <button
              onClick={() => setShowOverview(true)}
              className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors text-sm text-slate-300 flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Project Overview
            </button>
            <button
              onClick={() => setShowDocs(true)}
              className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors text-sm text-slate-300 flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
              Project Documentation
            </button>
            <button
              onClick={() => setShowSchema(true)}
              className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors text-sm text-slate-300 flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
                />
              </svg>
              Database Schema
            </button>
          </div>
        </div>

        {/* Settings */}
        <div className="border-t border-slate-800 p-4">
          <button className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors text-sm text-slate-300 flex items-center gap-2">
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            Settings
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 relative flex flex-col min-h-0">
        {showOverview && (
          <div className="absolute inset-0 z-40 bg-black/70 backdrop-blur-sm overflow-y-auto">
            <div className="max-w-4xl mx-auto my-10 px-6">
              <div className="bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">
                      Project Overview
                    </p>
                    <h2 className="text-2xl font-semibold text-white">
                      Quant Magic: S&amp;P 500 Query Intelligence
                    </h2>
                  </div>
                  <button
                    onClick={() => setShowOverview(false)}
                    className="text-slate-300 hover:text-white rounded-lg p-2 hover:bg-slate-800 transition-colors"
                    aria-label="Close project overview"
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
                <div className="grid gap-4">
                  {OVERVIEW_SECTIONS.map((section) => (
                    <div key={section.title} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                      <h3 className="text-lg font-semibold text-white mb-2">
                        {section.title}
                      </h3>
                      <ul className="space-y-2 text-sm text-slate-200 leading-relaxed">
                        {section.items.map((item) => (
                          <li key={item} className="flex gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
                <div className="mt-5 text-sm text-slate-300">
                  Need the full details?{" "}
                  <a
                    href={README_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="text-emerald-300 hover:text-emerald-200 underline"
                  >
                    Open the README
                  </a>{" "}
                  for architecture, commands, and data layout.
                </div>
              </div>
            </div>
          </div>
        )}
        {showDocs && (
          <div className="absolute inset-0 z-40 bg-black/70 backdrop-blur-sm overflow-y-auto">
            <div className="max-w-4xl mx-auto my-10 px-6">
              <div className="bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">
                      Project Documentation
                    </p>
                    <h2 className="text-2xl font-semibold text-white">
                      How Quant Magic is built and run
                    </h2>
                  </div>
                  <button
                    onClick={() => setShowDocs(false)}
                    className="text-slate-300 hover:text-white rounded-lg p-2 hover:bg-slate-800 transition-colors"
                    aria-label="Close project documentation"
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
                <div className="grid gap-4">
                  {DOCS_SECTIONS.map((section) => (
                    <div key={section.title} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                      <h3 className="text-lg font-semibold text-white mb-2">
                        {section.title}
                      </h3>
                      <ul className="space-y-2 text-sm text-slate-200 leading-relaxed">
                        {section.items.map((item) => (
                          <li key={item} className="flex gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
                <div className="mt-5 text-sm text-slate-300">
                  Looking for source details? See the README in the repo for full commands and architecture notes.
                </div>
              </div>
            </div>
          </div>
        )}
        {showSchema && (
          <div className="absolute inset-0 z-40 bg-black/70 backdrop-blur-sm overflow-y-auto">
            <div className="max-w-4xl mx-auto my-10 px-6">
              <div className="bg-[#0f172a] border border-slate-700 rounded-2xl shadow-2xl p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">
                      Data & Schema
                    </p>
                    <h2 className="text-2xl font-semibold text-white">
                      How the S&P 500 data is organized
                    </h2>
                  </div>
                  <button
                    onClick={() => setShowSchema(false)}
                    className="text-slate-300 hover:text-white rounded-lg p-2 hover:bg-slate-800 transition-colors"
                    aria-label="Close schema"
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
                <div className="grid gap-4">
                  {SCHEMA_SECTIONS.map((section) => (
                    <div key={section.title} className="bg-slate-900/60 border border-slate-800 rounded-xl p-4">
                      <h3 className="text-lg font-semibold text-white mb-2">
                        {section.title}
                      </h3>
                      <ul className="space-y-2 text-sm text-slate-200 leading-relaxed">
                        {section.items.map((item) => (
                          <li key={item} className="flex gap-2">
                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-400 flex-shrink-0" />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
                <div className="mt-5 text-sm text-slate-300">
                  Need exact SQL or columns? The UI shows executed SQL per answer, and the README documents the parquet catalogs.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Header */}
        <div className="bg-[#0a0a0a] border-b border-slate-800 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-white mb-1">
                Quant Magic
              </h1>
              <p className="text-sm text-slate-400">
                Ask questions about S&P 500 financial data
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${healthBadgeClass}`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${healthDotClass}`}
                />
                <div className="flex flex-col">
                  <span>{healthLabel}</span>
                  {health.message && (
                    <span className="text-[10px] text-slate-300">
                      {health.message}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-8 py-6 min-h-0">
          {selectedContextLabel && (
            <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-400">Context:</span>
              <span className="px-3 py-1 rounded-full bg-slate-800 text-slate-100 border border-slate-700">
                {selectedContextLabel}
              </span>
            </div>
          )}
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-2xl">
                <div className="w-16 h-16 bg-gradient-to-br from-brand-dark to-brand rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <svg
                    className="w-8 h-8 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                </div>
                <h2 className="text-2xl font-semibold text-white mb-3">
                  Welcome to Quant Magic
                </h2>
                <p className="text-slate-400">
                  Start a conversation by asking a question about S&P 500
                  companies, their financials, or sector analysis.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-6 max-w-4xl mx-auto">
              {messages.map((message) => {
                const presentation = message.metadata?.presentation;
                const reasoningTrace = message.metadata?.reasoningTrace;
                const narrative = presentation?.narrative ?? message.content;
                const highlights = presentation?.highlights ?? [];
                const table = presentation?.table ?? null;
                const tableColumns =
                  table && table.rows.length
                    ? table.columns && table.columns.length > 0
                      ? table.columns
                      : Object.keys(table.rows[0] as Record<string, unknown>)
                    : [];
                const formatterWarnings =
                  message.metadata?.warnings ?? presentation?.warnings ?? [];
                const durationSeconds =
                  typeof message.metadata?.totalTimeSeconds === "number"
                    ? (message.metadata.totalTimeSeconds as number)
                    : null;
                const rowCount =
                  typeof message.metadata?.rowCount === "number"
                    ? (message.metadata.rowCount as number)
                    : null;
                const requestId = message.metadata?.requestId;
                const isLoading = message.status === "loading";
                const isError =
                  message.status === "error" || Boolean(message.metadata?.error);
                const sqlExpanded = Boolean(sqlPanelOpen[message.id]);
                const sqlHint =
                  message.metadata?.sqlHint ||
                  reasoningTrace?.summary ||
                  "View generated SQL";
                const sqlValue = message.metadata?.sql;

                return (
                  <div key={message.id}>
                    {message.role === "user" ? (
                      <div className="flex justify-end">
                        <div className="max-w-3xl">
                          <div className="bg-gradient-to-r from-chat-user-from to-chat-user-to rounded-2xl px-6 py-4 shadow-lg">
                            <p className="text-white text-base leading-relaxed">
                              {message.content}
                            </p>
                          </div>
                          <div className="text-xs text-slate-500 mt-2 text-right">
                            {message.timestamp}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-4">
                        <div className="w-8 h-8 bg-gradient-to-br from-brand-dark to-brand rounded-lg flex items-center justify-center flex-shrink-0">
                          <span className="text-white font-bold text-sm">
                            A
                          </span>
                        </div>
                        <div className="flex-1 max-w-3xl">
                          <div className="bg-[#1e293b] rounded-2xl px-6 py-4 shadow-lg border border-slate-700/50">
                            {isLoading ? (
                              <div className="space-y-2">
                                <h3 className="text-slate-300 font-semibold">
                                  Thinking…
                                </h3>
                                <div className="text-sm text-slate-400 leading-relaxed whitespace-pre-line">
                                  {message.content}
                                </div>
                              </div>
                            ) : (
                              <div className="flex items-start gap-3 mb-4">
                                <div className="w-6 h-6 bg-brand rounded flex-shrink-0 mt-1" />
                                <div className="flex-1">
                                  <h3 className="text-white font-semibold mb-2">
                                    Business Summary & Key Findings
                                  </h3>
                                  <p className="text-slate-200 text-base leading-relaxed">
                                    {narrative}
                                  </p>
                                </div>
                              </div>
                            )}

                            {isError && (
                              <div className="mb-4 rounded-lg border border-rose-700 bg-rose-900/30 px-4 py-3 text-sm text-rose-100">
                                <p className="font-semibold">We couldn’t finish this answer.</p>
                                <p className="text-rose-50">
                                  {message.metadata?.error || message.content}
                                </p>
                                {requestId && (
                                  <p className="text-xs text-rose-100/80 mt-1">
                                    Request ID: {requestId}
                                  </p>
                                )}
                              </div>
                            )}

                            {highlights.length > 0 && (
                              <div className="mt-4">
                                <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">
                                  Highlights
                                </h4>
                                <ul className="list-disc list-inside text-slate-200 text-sm space-y-1">
                                  {highlights.map((item, idx) => (
                                    <li key={`${message.id}-highlight-${idx}`}>
                                      {item}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}

                            {table && table.rows.length > 0 && (
                              <div className="mt-4">
                                <h4 className="text-sm font-semibold uppercase tracking-wide text-slate-400 mb-2">
                                  Top rows
                                </h4>
                                <div className="overflow-x-auto rounded-lg border border-slate-700">
                                  <table className="min-w-full divide-y divide-slate-700 text-sm text-slate-200">
                                    <thead className="bg-slate-800/50">
                                      <tr>
                                        {tableColumns.map((column) => (
                                          <th
                                            key={`${message.id}-col-${column}`}
                                            className="px-3 py-2 text-left font-semibold uppercase text-[10px] tracking-wide text-slate-400"
                                          >
                                            {column}
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {table.rows.map((row, rowIdx) => (
                                        <tr
                                          key={`${message.id}-row-${rowIdx}`}
                                          className="odd:bg-slate-800/25"
                                        >
                                          {tableColumns.map((column) => {
                                            const cell =
                                              (row as Record<string, unknown>)[
                                                column
                                              ];
                                            const displayValue =
                                              cell === null ||
                                              cell === undefined
                                                ? "—"
                                                : String(cell);
                                            return (
                                              <td
                                                key={`${message.id}-${column}-${rowIdx}`}
                                                className="px-3 py-2 whitespace-nowrap align-top"
                                              >
                                                {displayValue}
                                              </td>
                                            );
                                          })}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                                {table.truncated && (
                                  <p className="text-xs text-amber-300 mt-2">
                                    Displaying only the first{" "}
                                    {table.rows.length} rows for brevity.
                                  </p>
                                )}
                              </div>
                            )}

                            {formatterWarnings.length > 0 && (
                              <div className="mt-4 text-xs text-amber-300">
                                {formatterWarnings.map((warning, idx) => (
                                  <p key={`${message.id}-warning-${idx}`}>
                                    ⚠️ {warning}
                                  </p>
                                ))}
                              </div>
                            )}

                            {(sqlValue || reasoningTrace) && (
                              <div className="mt-4 border border-slate-700 rounded-xl overflow-hidden">
                                <button
                                  type="button"
                                  onClick={() => toggleSqlPanel(message.id)}
                                  className="w-full flex items-center justify-between px-4 py-3 bg-slate-800/40 text-left text-sm text-slate-200"
                                >
                                  <div>
                                    <p className="font-semibold">
                                      Reasoning & SQL
                                    </p>
                                    <p className="text-xs text-slate-400">
                                      {sqlHint}
                                    </p>
                                  </div>
                                  <svg
                                    className={`w-4 h-4 transition-transform ${
                                      sqlExpanded ? "rotate-90" : ""
                                    }`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M9 5l7 7-7 7"
                                    />
                                  </svg>
                                </button>
                                {sqlExpanded && (
                                  <div className="px-4 py-3 space-y-3">
                                    {reasoningTrace && (
                                      <div className="text-xs text-slate-300 space-y-1">
                                        <p>
                                          <span className="font-semibold">
                                            Template:
                                          </span>{" "}
                                          {reasoningTrace.template_id ??
                                            "Not provided"}
                                        </p>
                                        <p>
                                          <span className="font-semibold">
                                            Method:
                                          </span>{" "}
                                          {reasoningTrace.generation_method ??
                                            "Unknown"}
                                        </p>
                                        {reasoningTrace.row_count !== null &&
                                          reasoningTrace.row_count !==
                                            undefined && (
                                            <p>
                                              <span className="font-semibold">
                                                Rows:
                                              </span>{" "}
                                              {reasoningTrace.row_count}
                                            </p>
                                          )}
                                        {reasoningTrace.warnings &&
                                          reasoningTrace.warnings.length > 0 && (
                                            <div className="text-amber-300">
                                              {reasoningTrace.warnings.map(
                                                (warning, idx) => (
                                                  <p
                                                    key={`${message.id}-trace-warning-${idx}`}
                                                  >
                                                    ⚠️ {warning}
                                                  </p>
                                                )
                                              )}
                                            </div>
                                          )}
                                      </div>
                                    )}
                                    {sqlValue ? (
                                      <pre className="bg-[#0a0a0a] rounded-lg p-4 text-xs text-slate-300 overflow-x-auto border border-slate-800">
                                        <code>{sqlValue}</code>
                                      </pre>
                                    ) : (
                                      <p className="text-xs text-slate-400">
                                        SQL not returned for this answer.
                                      </p>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}

                            {(durationSeconds !== null || rowCount !== null) && (
                              <div className="mt-4 flex gap-6 text-sm text-slate-400">
                                {durationSeconds !== null && (
                                  <div>
                                    <span className="font-semibold">
                                      Total time:
                                    </span>{" "}
                                    {durationSeconds.toFixed(3)} seconds
                                  </div>
                                )}
                                {rowCount !== null && (
                                  <div>
                                    <span className="font-semibold">
                                      Rows:
                                    </span>{" "}
                                    {rowCount}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          <div className="text-xs text-slate-500 mt-2 space-y-1">
                            <p>{message.timestamp}</p>
                            {requestId && (
                              <p className="text-slate-500">Request ID: {requestId}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
              {loading && (
                <div className="flex gap-4">
                  <div className="w-8 h-8 bg-gradient-to-br from-brand-dark to-brand rounded-lg flex items-center justify-center flex-shrink-0">
                    <span className="text-white font-bold text-sm">A</span>
                  </div>
                  <div className="flex-1 max-w-3xl">
                    <div className="bg-[#1e293b] rounded-2xl px-6 py-4 shadow-lg border border-slate-700/50">
                      <div className="flex items-center gap-3">
                        <div className="flex gap-1">
                          <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                          <div
                            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.1s" }}
                          ></div>
                          <div
                            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
                            style={{ animationDelay: "0.2s" }}
                          ></div>
                        </div>
                        <span className="text-slate-400 text-sm">
                          Thinking...
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-800 bg-[#0a0a0a] p-6">
          {starterQuestions.length > 0 && (
            <div className="max-w-4xl mx-auto mb-3">
              <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">
                Suggested questions
              </div>
              <div className="flex flex-wrap gap-2">
                {starterQuestions.map((starter, idx) => (
                  <button
                    key={`starter-${idx}`}
                    type="button"
                    onClick={() => handleStarterClick(starter)}
                    className="px-3 py-2 rounded-lg bg-slate-800/70 text-slate-100 text-sm border border-slate-700 hover:border-brand hover:text-white transition-colors"
                    disabled={loading}
                  >
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          )}
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="flex gap-3 items-center">
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={question}
                  onChange={handleTextareaChange}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(
                        e as unknown as FormEvent<HTMLFormElement>
                      );
                    }
                  }}
                  placeholder="Type your message here..."
                  className="w-full bg-[#1e293b] border border-slate-700 rounded-xl px-4 py-3 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent resize-none min-h-[52px] max-h-[200px]"
                  rows={1}
                  disabled={loading}
                />
              </div>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="flex items-center justify-center w-12 h-12 bg-gradient-to-r from-brand-dark to-brand hover:from-brand hover:to-brand-light disabled:from-slate-700 disabled:to-slate-700 disabled:cursor-not-allowed text-white rounded-xl transition-all shadow-lg disabled:shadow-none translate-y-[1px]"
              >
                {loading ? (
                  <svg
                    className="animate-spin h-5 w-5"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    ></circle>
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    ></path>
                  </svg>
                ) : (
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M13 7l5 5m0 0l-5 5m5-5H6"
                    />
                  </svg>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default App;
