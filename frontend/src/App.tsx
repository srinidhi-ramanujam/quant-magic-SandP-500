import { useState, useRef, useEffect } from "react";
import type { FormEvent } from "react";

type PresentationTable = {
  columns: string[];
  rows: Record<string, unknown>[];
  truncated?: boolean;
};

type PresentationPayload = {
  narrative: string;
  highlights?: string[];
  table?: PresentationTable | null;
  warnings?: string[];
};

type ReasoningTrace = {
  template_id?: string | null;
  generation_method?: string | null;
  row_count?: number | null;
  summary?: string | null;
  warnings?: string[];
};

type ConversationTurnPayload = {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
};

type Message = {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: string;
  metadata?: {
    sql?: string | null;
    total_time_seconds?: number;
    row_count?: number;
    presentation?: PresentationPayload | null;
    reasoning_trace?: ReasoningTrace | null;
    sql_hint?: string | null;
  };
};

type ChatSession = {
  id: string;
  title: string;
  timestamp: string;
};

type QueryResponse = {
  answer: string;
  success: boolean;
  sql?: string | null;
  metadata: Record<string, unknown>;
  sources?: string[] | null;
  error?: string | null;
  presentation?: PresentationPayload | null;
  reasoning_trace?: ReasoningTrace | null;
  sql_collapsible_hint?: string | null;
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
    role: message.type,
    content: message.content,
    timestamp: message.timestamp,
  }));
};

function App() {
  const [question, setQuestion] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatSession[]>([]);
  const [sqlPanelOpen, setSqlPanelOpen] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Check API connection on mount
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch("/api/health");
        setApiConnected(response.ok);
      } catch {
        setApiConnected(false);
      }
    };
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleSqlPanel = (id: string) => {
    setSqlPanelOpen((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!question.trim() || loading) {
      return;
    }

    const trimmedQuestion = question.trim();
    const historyPayload = buildHistoryPayload(messages);
    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: trimmedQuestion,
      timestamp: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);
    logInfo("question", {
      id: userMessage.id,
      question: trimmedQuestion,
    });

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: trimmedQuestion,
          history: historyPayload,
          include_formatted_answer: true,
        }),
      });

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        throw new Error(
          errorPayload?.detail ||
            `API error (${response.status} ${response.statusText})`,
        );
      }

      const payload = (await response.json()) as QueryResponse;

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: payload.answer,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
        metadata: {
          sql: payload.sql,
          total_time_seconds: payload.metadata
            ?.total_time_seconds as number,
          row_count: payload.metadata?.row_count as number,
          presentation: payload.presentation ?? null,
          reasoning_trace: payload.reasoning_trace ?? null,
          sql_hint: payload.sql_collapsible_hint ?? null,
        },
      };

      setMessages((prev) => [...prev, assistantMessage]);
      logInfo("response", {
        id: assistantMessage.id,
        requestId: payload.metadata?.request_id,
        success: payload.success,
        sql: payload.sql,
      });

      // Add to chat history if it's the first message in the session
      if (messages.length === 0) {
        const newSession: ChatSession = {
          id: Date.now().toString(),
          title: userMessage.content.slice(0, 50) + "...",
          timestamp: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        };
        setChatHistory((prev) => [newSession, ...prev]);
      }
    } catch (err) {
      console.error("[ui] error", err);
      const errorText =
        err instanceof Error
          ? err.message
          : "Unable to reach the API. Please confirm the backend is running.";
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: errorText,
        timestamp: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleTextareaChange = (
    event: React.ChangeEvent<HTMLTextAreaElement>
  ) => {
    setQuestion(event.target.value);
    // Auto-resize textarea
    event.target.style.height = "auto";
    event.target.style.height = event.target.scrollHeight + "px";
  };

  const handleNewChat = () => {
    setMessages([]);
    setQuestion("");
  };

  return (
    <div className="flex h-screen bg-[#0a0a0a] text-slate-100">
      {/* Left Sidebar */}
      <div className="w-80 bg-[#111111] border-r border-slate-800 flex flex-col">
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

        {/* New Chat Button */}
        <div className="p-4">
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
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 py-2">
            <div className="flex items-center gap-2 text-slate-400 text-sm mb-2">
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
              Chat History
            </div>
            <div className="space-y-1">
              {chatHistory.map((chat) => (
                <button
                  key={chat.id}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-slate-800/50 transition-colors text-sm text-slate-300 truncate"
                >
                  <div className="flex items-start gap-2">
                    <svg
                      className="w-4 h-4 mt-0.5 flex-shrink-0"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                      />
                    </svg>
                    <div className="flex-1 min-w-0">
                      <div className="truncate">{chat.title}</div>
                      <div className="text-xs text-slate-500">
                        {chat.timestamp}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
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
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Project Documentation
            </button>
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
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                />
              </svg>
              API Documentation
            </button>
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
      <div className="flex-1 flex flex-col">
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
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
                  apiConnected
                    ? "bg-emerald-500/20 text-emerald-300"
                    : "bg-red-500/20 text-red-300"
                }`}
              >
                <div
                  className={`w-2 h-2 rounded-full ${
                    apiConnected ? "bg-emerald-400" : "bg-red-400"
                  }`}
                />
                {apiConnected ? "API Connected" : "API Disconnected"}
              </div>
            </div>
          </div>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
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
                const reasoningTrace = message.metadata?.reasoning_trace;
                const narrative = presentation?.narrative ?? message.content;
                const highlights = presentation?.highlights ?? [];
                const table = presentation?.table ?? null;
                const tableColumns =
                  table && table.rows.length
                    ? table.columns && table.columns.length > 0
                      ? table.columns
                      : Object.keys(table.rows[0] as Record<string, unknown>)
                    : [];
                const formatterWarnings = presentation?.warnings ?? [];
                const durationSeconds =
                  typeof message.metadata?.total_time_seconds === "number"
                    ? (message.metadata.total_time_seconds as number)
                    : null;
                const rowCount =
                  typeof message.metadata?.row_count === "number"
                    ? (message.metadata.row_count as number)
                    : null;
                const sqlExpanded = Boolean(sqlPanelOpen[message.id]);
                const sqlHint =
                  message.metadata?.sql_hint ||
                  reasoningTrace?.summary ||
                  "View generated SQL";

                return (
                  <div key={message.id}>
                    {message.type === "user" ? (
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

                            {message.metadata?.sql && (
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
                                    <pre className="bg-[#0a0a0a] rounded-lg p-4 text-xs text-slate-300 overflow-x-auto border border-slate-800">
                                      <code>{message.metadata.sql}</code>
                                    </pre>
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
                          <div className="text-xs text-slate-500 mt-2">
                            {message.timestamp}
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
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
            <div className="flex gap-3 items-end">
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
                className="flex items-center justify-center w-12 h-12 bg-gradient-to-r from-brand-dark to-brand hover:from-brand hover:to-brand-light disabled:from-slate-700 disabled:to-slate-700 disabled:cursor-not-allowed text-white rounded-xl transition-all shadow-lg disabled:shadow-none"
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
