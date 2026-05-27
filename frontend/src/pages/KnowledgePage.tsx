import { useEffect, useMemo, useState } from "react";

import {
  addKnowledgeSource,
  answerWithKnowledge,
  fetchSettings,
  fetchKnowledgeSummary,
  pickWorkingDirectory,
  reindexKnowledge,
  removeKnowledgeSource,
  runKnowledgeQuery,
} from "../lib/api";
import { resolveSelectedWorkflowPreset } from "../lib/workflowPresets";
import type {
  KnowledgeAnswerPayload,
  KnowledgeQueryPayload,
  KnowledgeSummaryPayload,
  SettingsPayload,
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

function triggerDownload(filename: string, payload: BlobPart, mimeType: string) {
  const blob = new Blob([payload], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 500);
}

export function KnowledgePage({ onOpenSearch }: { onOpenSearch: () => void }) {
  const [summary, setSummary] = useState<KnowledgeSummaryPayload | null>(null);
  const [sourcePath, setSourcePath] = useState("");
  const [sourceCollection, setSourceCollection] = useState("");
  const [sourceTags, setSourceTags] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<KnowledgeMode>("documents-only");
  const [collectionFilter, setCollectionFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [queryPayload, setQueryPayload] = useState<KnowledgeQueryPayload | null>(null);
  const [answerPayload, setAnswerPayload] = useState<KnowledgeAnswerPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string>("");
  const [settingsPayload, setSettingsPayload] = useState<SettingsPayload | null>(null);

  async function loadSummary() {
    const [payload, nextSettings] = await Promise.all([fetchKnowledgeSummary(), fetchSettings()]);
    setSummary(payload);
    setSettingsPayload(nextSettings);
    if (!settingsPayload) {
      setMode(resolveSelectedWorkflowPreset(nextSettings)?.knowledgeDefaults.mode || "documents-only");
    }
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
  const currentWorkflowPreset = useMemo(
    () => resolveSelectedWorkflowPreset(settingsPayload),
    [settingsPayload],
  );

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
        {currentWorkflowPreset ? (
          <p className="helper-text">
            Workflow preset: {currentWorkflowPreset.label} | {currentWorkflowPreset.summary}
          </p>
        ) : null}
        <div className="summary-metrics">
          <span>Sources: {summary.sourceCount}</span>
          <span>Documents: {summary.documentCount}</span>
          <span>Indexed: {summary.indexedDocumentCount}</span>
          <span>Errors: {summary.errorCount}</span>
        </div>
        <p className="helper-text">Podrzani formati: {extensionLine}</p>
        <p className="helper-text">{summary.reindexStatus.summary}</p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Sources</span>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Collection</span>
            <input
              type="text"
              value={sourceCollection}
              onChange={(event) => setSourceCollection(event.target.value)}
              placeholder="Manuals, Notes, Projects..."
            />
          </label>
          <label className="settings-compact-field settings-medium-field">
            <span>Tags</span>
            <input
              type="text"
              value={sourceTags}
              onChange={(event) => setSourceTags(event.target.value)}
              placeholder="gpu, llama, coding"
            />
          </label>
        </div>
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
                const result = await addKnowledgeSource(sourcePath, {
                  collection: sourceCollection,
                  tags: sourceTags
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean),
                });
                if (result.status !== "ok") {
                  throw new Error(result.summary || "Knowledge source nije dodat.");
                }
                setSourcePath("");
                setSourceCollection("");
                setSourceTags("");
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
                      Collection: {item.collection || "--"} | Tags:{" "}
                      {item.tags.length ? item.tags.join(", ") : "--"}
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
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Collections</span>
            <select value={collectionFilter} onChange={(event) => setCollectionFilter(event.target.value)}>
              <option value="">All collections</option>
              {summary.collections.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="settings-compact-field">
            <span>Tags</span>
            <select value={tagFilter} onChange={(event) => setTagFilter(event.target.value)}>
              <option value="">All tags</option>
              {summary.tags.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="settings-action-row">
          <select value={mode} onChange={(event) => setMode(event.target.value as KnowledgeMode)}>
            <option value="documents-only">Documents only</option>
            <option value="documents+web">Documents + web</option>
            <option value="web-only">Web only</option>
          </select>
          <input
            className="settings-path-input"
            placeholder={
              currentWorkflowPreset?.knowledgeDefaults.queryHint ||
              "Upisi pitanje za knowledge query ili answer"
            }
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
                const payload = await runKnowledgeQuery(query, {
                  collection: collectionFilter,
                  tag: tagFilter,
                });
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
                const payload = await answerWithKnowledge(query, mode, {
                  collection: collectionFilter,
                  tag: tagFilter,
                });
                setAnswerPayload(payload);
                setQueryPayload({
                  status: payload.status,
                  query: payload.query,
                  collection: payload.collection,
                  tag: payload.tag,
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
                    <div className="muted-line">
                      Collection: {item.collection || "--"} | Tags:{" "}
                      {item.tags.length ? item.tags.join(", ") : "--"}
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
        {answerPayload ? (
          <>
            <p className="helper-text">
              Collections: {answerPayload.usedCollections.length ? answerPayload.usedCollections.join(", ") : "--"} |
              Tags: {answerPayload.usedTags.length ? answerPayload.usedTags.join(", ") : "--"}
            </p>
            <div className="inline-actions">
              <button
                type="button"
                onClick={() =>
                  triggerDownload(
                    "knowledge-answer.json",
                    JSON.stringify(answerPayload, null, 2),
                    "application/json",
                  )
                }
              >
                Export JSON
              </button>
              <button
                type="button"
                onClick={() =>
                  triggerDownload(
                    "knowledge-answer.md",
                    [
                      `# Knowledge answer\n\n`,
                      `Query: ${answerPayload.query}\n\n`,
                      `Mode: ${answerPayload.mode}\n\n`,
                      `${answerPayload.answer}\n\n`,
                      `## Citations\n`,
                      ...answerPayload.citations.map(
                        (citation) =>
                          `- [${citation.index}] ${citation.name} | ${citation.collection || "--"} | ${citation.path}\n`,
                      ),
                    ].join(""),
                    "text/markdown",
                  )
                }
              >
                Export Markdown
              </button>
            </div>
          </>
        ) : null}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Citations</span>
        {answerPayload?.citations?.length ? (
          <div className="model-list">
            {answerPayload.citations.map((citation) => (
              <article className="model-item" key={`${citation.index}-${citation.path}`}>
                <div className="model-item-header">
                  <div>
                    <strong>
                      [{citation.index}] {citation.name}
                    </strong>
                    <div className="muted-line">
                      {citation.collection || "--"} | {citation.tags.length ? citation.tags.join(", ") : "--"}
                    </div>
                    <div className="muted-line">{citation.path}</div>
                    <p className="helper-text">{citation.snippet}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">
            Kad knowledge answer koristi lokalne dokumente, ovde ces videti which docs were used i
            njihove citate.
          </p>
        )}
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
