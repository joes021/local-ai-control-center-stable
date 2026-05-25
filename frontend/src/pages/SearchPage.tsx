import { useEffect, useMemo, useState } from "react";

import {
  answerWithLocalModel,
  fetchSearchSummary,
  runSearchQuery,
} from "../lib/api";
import type {
  SearchAnswerPayload,
  SearchQueryPayload,
  SearchSummaryPayload,
} from "../lib/types";


function renderSearchModeLabel(mode: string, prefix: string) {
  if (mode === "always") {
    return "Always";
  }
  if (mode === "on-demand") {
    return `On-demand (${prefix})`;
  }
  return "Off";
}

function formatUsage(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }
  return String(value);
}

export function SearchPage() {
  const [summary, setSummary] = useState<SearchSummaryPayload | null>(null);
  const [query, setQuery] = useState("");
  const [searchPayload, setSearchPayload] = useState<SearchQueryPayload | null>(null);
  const [answerPayload, setAnswerPayload] = useState<SearchAnswerPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingAnswer, setLoadingAnswer] = useState(false);

  async function loadSummary() {
    const payload = await fetchSearchSummary();
    setSummary(payload);
  }

  useEffect(() => {
    void loadSummary().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Search summary nije mogao da se ucita.");
    });
  }, []);

  const currentSettingsLine = useMemo(() => {
    if (!summary) {
      return "";
    }
    return `Mode: ${renderSearchModeLabel(summary.settings.mode, summary.settings.promptPrefix)} | Provider: ${summary.settings.provider} | Base URL: ${summary.settings.baseUrl}`;
  }, [summary]);

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!summary) {
    return <section className="status-card wide-card">Ucitavam Search workspace...</section>;
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Search workspace</span>
        <strong className="status-value">SearxNG + lokalni model + OpenCode local-lacc</strong>
        <p className="helper-text">{currentSettingsLine}</p>
        <p className="helper-text">
          Ovaj tab koristi isti shared search sloj kao i OpenCode `local-lacc` provider. Cloud
          `opencode` modeli ne prolaze kroz ovaj lokalni proxy put.
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Web query</span>
        <div className="settings-action-row">
          <input
            className="settings-path-input"
            placeholder="Upisi pitanje ili temu za web search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="button"
            disabled={loadingSearch || !query.trim()}
            onClick={async () => {
              setLoadingSearch(true);
              setError(null);
              try {
                const payload = await runSearchQuery(query);
                setSearchPayload(payload);
                setAnswerPayload(null);
                await loadSummary();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Web search nije uspeo.");
              } finally {
                setLoadingSearch(false);
              }
            }}
          >
            {loadingSearch ? "Searching..." : "Search web"}
          </button>
          <button
            type="button"
            disabled={loadingAnswer || !query.trim()}
            onClick={async () => {
              setLoadingAnswer(true);
              setError(null);
              try {
                const payload = await answerWithLocalModel(query);
                setAnswerPayload(payload);
                setSearchPayload(payload);
                await loadSummary();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Lokalni odgovor nije uspeo.");
              } finally {
                setLoadingAnswer(false);
              }
            }}
          >
            {loadingAnswer ? "Answering..." : "Answer with local model"}
          </button>
        </div>
        <p className="helper-text">
          `Search web` vraca rezultate. `Answer with local model` prvo radi isti web search, pa onda
          salje rezultate kao dodatni context aktivnom lokalnom runtime-u.
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Search results</span>
        <strong className="status-value">{searchPayload?.summary || "Jos nema rezultata."}</strong>
        {searchPayload?.results?.length ? (
          <div className="model-list">
            {searchPayload.results.map((item) => (
              <article className="model-item" key={`${item.url}-${item.title}`}>
                <div className="model-item-header">
                  <div>
                    <strong>{item.title}</strong>
                    <div className="muted-line">{item.url}</div>
                    <p className="helper-text">{item.snippet}</p>
                    <div className="muted-line">Engine: {item.engine}</div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Kad pokrenes query, ovde ce se pojaviti normalizovani web rezultati.</p>
        )}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Local answer</span>
        <strong className="status-value">{answerPayload?.answer || "Jos nema lokalnog odgovora."}</strong>
        <div className="summary-metrics">
          <span>Runtime: {answerPayload?.answerRuntime || "--"}</span>
          <span>Model: {answerPayload?.answerModel || "--"}</span>
          <span>Prompt tokens: {formatUsage(answerPayload?.usage?.promptTokens)}</span>
          <span>Completion tokens: {formatUsage(answerPayload?.usage?.completionTokens)}</span>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Recent search history</span>
        {summary.history.length ? (
          <div className="model-list">
            {summary.history.map((item) => (
              <article className="model-item" key={`${item.askedAt}-${item.query}`}>
                <div className="model-item-header">
                  <div>
                    <strong>{item.query}</strong>
                    <div className="muted-line">
                      {item.mode} | {item.resultCount} result(a) | {item.askedAt}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Direktni Search tab query i answer tok upisuju se ovde kao lokalna istorija.</p>
        )}
      </section>
    </>
  );
}
