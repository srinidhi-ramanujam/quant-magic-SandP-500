import { useState } from "react";
import type { FormEvent } from "react";

type QueryResponse = {
  answer: string;
  success: boolean;
  sql?: string | null;
  metadata: Record<string, unknown>;
  sources?: string[] | null;
  error?: string | null;
};

const SAMPLE_QUESTION =
  "How many companies are in the Technology sector for the S&P 500?";

function App() {
  const [question, setQuestion] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!question.trim()) {
      setError("Please enter a question to run through the pipeline.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question }),
      });

      const payload = (await response.json()) as QueryResponse;
      setResult(payload);
    } catch (err) {
      console.error(err);
      setResult(null);
      setError("Unable to reach the API. Confirm the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen justify-center bg-slate-950 px-4 py-12 text-slate-100">
      <div className="w-full max-w-3xl space-y-10">
        <header className="space-y-3 text-center sm:text-left">
          <p className="inline-flex items-center gap-2 rounded-full border border-brand-dark/60 bg-brand-dark/40 px-3 py-1 text-xs font-medium uppercase tracking-wide text-brand-light">
            Quant Magic Preview
          </p>
          <h1 className="text-3xl font-semibold text-white sm:text-4xl">
            Ask the S&amp;P 500 knowledge base
          </h1>
          <p className="text-sm text-slate-400 sm:text-base">
            Run a natural language question through the Azure-backed pipeline.
            Answers are generated live via the FastAPI service you can expose
            from this Codespace.
          </p>
        </header>

        <section className="rounded-2xl border border-slate-800/60 bg-slate-900/60 p-6 shadow-2xl shadow-brand-dark/20 backdrop-blur">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <label className="block space-y-2">
              <span className="text-sm font-semibold uppercase tracking-wide text-slate-300">
                Question
              </span>
              <textarea
                className="w-full min-h-[140px] resize-y rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-base text-slate-100 placeholder:text-slate-500 focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand/40 transition"
                placeholder={SAMPLE_QUESTION}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
              />
            </label>

            {error && (
              <p className="rounded-lg border border-red-500/50 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                {error}
              </p>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light/40 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Thinking..." : "Ask Question"}
              </button>
              <button
                type="button"
                className="text-sm font-medium text-brand-light underline-offset-4 hover:underline"
                onClick={() => setQuestion(SAMPLE_QUESTION)}
              >
                Use sample question
              </button>
            </div>
          </form>
        </section>

        {result && (
          <section className="space-y-4 rounded-2xl border border-slate-800/60 bg-slate-900/70 p-6 shadow-inner shadow-black/30">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-xl font-semibold text-white">Answer</h2>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${result.success ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/10 text-red-300"}`}
              >
                {result.success ? "Success" : "Error"}
              </span>
            </div>

            <p className="text-base leading-relaxed text-slate-200">
              {result.answer}
            </p>

            {result.sql && (
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                  SQL
                </h3>
                <pre className="mt-2 max-h-48 overflow-x-auto overflow-y-auto rounded-xl border border-slate-800 bg-slate-950/80 p-4 text-sm text-slate-200">
                  <code>{result.sql}</code>
                </pre>
              </div>
            )}

            <dl className="grid gap-3 text-sm text-slate-400 sm:grid-cols-2">
              <div>
                <dt className="font-semibold uppercase tracking-wide text-slate-500">
                  Total time
                </dt>
                <dd>
                  {((result.metadata?.total_time_seconds as number) ?? 0).toFixed(
                    3,
                  )}{" "}
                  seconds
                </dd>
              </div>
              <div>
                <dt className="font-semibold uppercase tracking-wide text-slate-500">
                  Rows
                </dt>
                <dd>{(result.metadata?.row_count as number) ?? 0}</dd>
              </div>
            </dl>

            {result.error && (
              <p className="rounded-lg border border-red-500/50 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                {result.error}
              </p>
            )}

            {result.sources && result.sources.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
                  Sources
                </h3>
                <ul className="mt-2 list-inside list-disc text-slate-300">
                  {result.sources.map((source) => (
                    <li key={source}>{source}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}

        <section className="rounded-2xl border border-slate-800/60 bg-slate-900/40 p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">
                API health check
              </h2>
              <p className="text-sm text-slate-400">
                HTMX hits the FastAPI health endpoint and injects the raw
                response below.
              </p>
            </div>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-200 transition hover:border-brand-light"
              hx-get="/api/health"
              hx-target="#health-status"
              hx-swap="text"
            >
              Refresh
            </button>
          </div>
          <div
            id="health-status"
            className="mt-4 rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-sm text-slate-300"
            hx-get="/api/health"
            hx-trigger="load"
            hx-swap="text"
          >
            Checking FastAPI service...
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;
