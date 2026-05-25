import { useEffect, useMemo, useState } from "react";

import {
  addKnowledgeSource,
  answerWithKnowledge,
  fetchKnowledgeSummary,
  pickWorkingDirectory,
  reindexKnowledge,
  removeKnowledgeSource,
  runKnowledgeQuery,
} from "../lib/api";
import type {
  KnowledgeAnswerPayload,
  KnowledgeQueryPayload,
  KnowledgeSummaryPayload,
} from "../lib/types";


type KnowledgeMode = "documents-only" | "documents+web" | "web-only";

function renderModeLabel(mode: KnowledgeMode) {
  if (mode === "documents+web") {
    return "Documents + web";
  }
  if (mode === "web-only") {
    return "Web only";
  }
  return "Documents only";
}

function formatUsage(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }
  return String(value);
}

export function KnowledgePage({ onOpenSearch }: { onOpenSearch: () => void }) {
  const [summary, setSummary] = useState<KnowledgeSummaryPayload | null>(null);
  const [sourcePath, setSourcePath] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<KnowledgeMode>("documents-only");
  const [queryPayload, setQueryPayload] = useState<KnowledgeQueryPayload | null>(null);
  const [answerPayload, setAnswerPayload] = useState<KnowledgeAnswerPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string>("");

  async function loadSummary() {
    const payload = await fetchKnowledgeSummary();
    setSummary(payload);
  }

  useEffect(() => {
    void loadSummary().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Knowledge workspace nije mogao da se ucita.");
    });
  }, []);

  const extensionLine = useMemo(() => {
    if (!summary) {
      return "";
    }
    return summary.supportedExtensions.join(", ");
  }, [summary]);

  async function refreshAfterAction() {
    await loadSummary();
  }

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!summary) {
    return <section className="status-card wide-card">Ucitavam Knowledge workspace...</section>;
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Knowledge workspace</span>
        <strong className="status-value">Lokalni dokumenti + opcioni web context</strong>
        <p className="helper-text">
          Ovaj tab indeksira lokalne fajlove installer-managed putem i omogucava `documents-only`,
          `documents+web` i `web-only` answer tok. Kada ti treba samo web sloj, mozes i direktno
          da otvoris Search tab.
        </p>
        <div className="summary-metrics">
          <span>Sources: {summary.sourceCount}</span>
          <span>Documents: {summary.documentCount}</span>
          <span>Indexed: {summary.indexedDocumentCount}</span>
          <span>Errors: {summary.errorCount}</span>
        </div>
        <p className="helper-text">Podrzani formati: {extensionLine}</p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Sources</span>
        <div className="settings-action-row">
          <input
            className="settings-path-input"
            placeholder="Unesi lokalni file ili folder path"
            value={sourcePath}
            onChange={(event) => setSourcePath(event.target.value)}
          />
          <button
            type="button"
            disabled={busyAction === "browse"}
            onClick={async () => {
              setBusyAction("browse");
              setError(null);
              try {
                const result = await pickWorkingDirectory();
                if (result.status === "ok" && result.path) {
                  setSourcePath(result.path);
                }
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Knowledge folder picker nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "browse" ? "Opening..." : "Browse"}
          </button>
          <button
            type="button"
            disabled={busyAction === "add" || !sourcePath.trim()}
            onClick={async () => {
              setBusyAction("add");
              setError(null);
              try {
                const result = await addKnowledgeSource(sourcePath);
                if (result.status !== "ok") {
                  throw new Error(result.summary || "Knowledge source nije dodat.");
                }
                setSourcePath("");
                await refreshAfterAction();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Knowledge source nije dodat.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "add" ? "Adding..." : "Add source"}
          </button>
          <button
            type="button"
            disabled={busyAction === "reindex" || summary.sourceCount === 0}
            onClick={async () => {
              setBusyAction("reindex");
              setError(null);
              try {
                const result = await reindexKnowledge();
                if (result.status !== "ok") {
                  throw new Error(result.summary || "Knowledge reindex nije uspeo.");
                }
                await refreshAfterAction();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Knowledge reindex nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "reindex" ? "Reindexing..." : "Reindex"}
          </button>
          <button type="button" onClick={onOpenSearch}>
            Open Search
          </button>
        </div>
        {summary.sources.length ? (
          <div className="model-list">
            {summary.sources.map((item) => (
              <article className="model-item" key={item.id}>
                <div className="model-item-header">
                  <div>
                    <strong>{item.path}</strong>
                    <div className="muted-line">
                      {item.kind} | {item.exists ? "exists" : "missing"} | documents: {item.documentCount} |
                      indexed: {item.indexedDocumentCount}
                    </div>
                    <div className="helper-text">
                      Skipped: {item.skippedCount} | Errors: {item.errorCount} | Last index:{" "}
                      {item.lastIndexedAt || "--"}
                    </div>
                    {item.lastError ? <div className="helper-text">{item.lastError}</div> : null}
                  </div>
                  <button
                    type="button"
                    disabled={busyAction === item.id}
                    onClick={async () => {
                      setBusyAction(item.id);
                      setError(null);
                      try {
                        const result = await removeKnowledgeSource(item.id);
                        if (result.status !== "ok") {
                          throw new Error(result.summary || "Knowledge source nije uklonjen.");
                        }
                        await refreshAfterAction();
                      } catch (reason: unknown) {
                        setError(reason instanceof Error ? reason.message : "Knowledge source nije uklonjen.");
                      } finally {
                        setBusyAction("");
                      }
                    }}
                  >
                    Remove
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Jos nema prijavljenih knowledge source-ova.</p>
        )}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Query + answer</span>
        <div className="settings-action-row">
          <select value={mode} onChange={(event) => setMode(event.target.value as KnowledgeMode)}>
            <option value="documents-only">Documents only</option>
            <option value="documents+web">Documents + web</option>
            <option value="web-only">Web only</option>
          </select>
          <input
            className="settings-path-input"
            placeholder="Upisi pitanje za knowledge query ili answer"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="button"
            disabled={busyAction === "query" || !query.trim()}
            onClick={async () => {
              setBusyAction("query");
              setError(null);
              try {
                const payload = await runKnowledgeQuery(query);
                setQueryPayload(payload);
                setAnswerPayload(null);
                await refreshAfterAction();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Knowledge query nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "query" ? "Searching..." : "Search docs"}
          </button>
          <button
            type="button"
            disabled={busyAction === "answer" || !query.trim()}
            onClick={async () => {
              setBusyAction("answer");
              setError(null);
              try {
                const payload = await answerWithKnowledge(query, mode);
                setAnswerPayload(payload);
                setQueryPayload({
                  status: payload.status,
                  query: payload.query,
                  resultCount: payload.documentResultCount,
                  summary: payload.summary,
                  results: payload.documentResults,
                  history: payload.history,
                });
                await refreshAfterAction();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Knowledge answer nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "answer" ? "Answering..." : `Answer (${renderModeLabel(mode)})`}
          </button>
        </div>
        <p className="helper-text">
          `Documents only` koristi samo lokalni indeks. `Documents + web` spaja lokalne dokumente sa
          istim shared SearxNG slojem koji koristi Search tab. `Web only` ovde ostaje samo zgodan
          handoff ka istom local-model web answer toku.
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Document results</span>
        <strong className="status-value">{queryPayload?.summary || "Jos nema document rezultata."}</strong>
        {queryPayload?.results?.length ? (
          <div className="model-list">
            {queryPayload.results.map((item) => (
              <article className="model-item" key={`${item.docId}-${item.path}`}>
                <div className="model-item-header">
                  <div>
                    <strong>{item.name}</strong>
                    <div className="muted-line">
                      {item.fileType} | score: {item.score.toFixed(2)} | chars: {item.charCount}
                    </div>
                    <div className="muted-line">{item.path}</div>
                    <p className="helper-text">{item.snippet}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Kad pokrenes knowledge query, ovde ce se pojaviti lokalni dokument pogoci.</p>
        )}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Knowledge answer</span>
        <strong className="status-value">{answerPayload?.answer || "Jos nema knowledge odgovora."}</strong>
        <div className="summary-metrics">
          <span>Mode: {answerPayload ? renderModeLabel(answerPayload.mode as KnowledgeMode) : "--"}</span>
          <span>Runtime: {answerPayload?.answerRuntime || "--"}</span>
          <span>Model: {answerPayload?.answerModel || "--"}</span>
          <span>Docs: {answerPayload?.documentResultCount ?? 0}</span>
          <span>Web: {answerPayload?.webResultCount ?? 0}</span>
          <span>Prompt tokens: {formatUsage(answerPayload?.usage?.promptTokens)}</span>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Recent knowledge history</span>
        {summary.history.length ? (
          <div className="model-list">
            {summary.history.map((item) => (
              <article className="model-item" key={`${item.askedAt}-${item.query}`}>
                <div className="model-item-header">
                  <div>
                    <strong>{item.query}</strong>
                    <div className="muted-line">
                      {item.mode} | docs: {item.documentResultCount} | web: {item.webResultCount} |{" "}
                      {item.askedAt}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Knowledge query i answer tok se upisuju ovde kao lokalna istorija.</p>
        )}
      </section>
    </>
  );
}
