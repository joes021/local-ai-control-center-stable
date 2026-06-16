import { useEffect, useMemo, useState } from "react";

import { CustomSelect } from "../components/CustomSelect";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { SupportPageDeck } from "../components/shell/SupportPageDeck";
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
    return "Dokumenti + veb";
  }
  if (mode === "web-only") {
    return "Samo veb";
  }
  return "Samo dokumenti";
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
      setError(reason instanceof Error ? reason.message : "Radni prostor znanja nije mogao da se učita.");
    });
  }, []);

  const extensionLine = useMemo(() => {
    if (!summary) {
      return "";
    }
    return summary.supportedExtensions.join(", ");
  }, [summary]);
  const collectionOptions = useMemo(
    () => [
      { value: "", label: "Sve kolekcije" },
      ...(summary?.collections ?? []).map((item) => ({ value: item, label: item })),
    ],
    [summary?.collections],
  );
  const tagOptions = useMemo(
    () => [
      { value: "", label: "Sve oznake" },
      ...(summary?.tags ?? []).map((item) => ({ value: item, label: item })),
    ],
    [summary?.tags],
  );
  const knowledgeModeOptions = useMemo(
    () => [
      { value: "documents-only", label: "Samo dokumenti" },
      { value: "documents+web", label: "Dokumenti + veb" },
      { value: "web-only", label: "Samo veb" },
    ],
    [],
  );
  const currentWorkflowPreset = useMemo(
    () => resolveSelectedWorkflowPreset(settingsPayload),
    [settingsPayload],
  );

  async function refreshAfterAction() {
    await loadSummary();
  }

  const inlineError = error;

  if (!summary) {
    return (
      <PageDataStateCard
        error={inlineError}
        loadingText="Učitavam radni prostor znanja..."
        onRetry={() => {
          setError(null);
          void loadSummary().catch((reason: unknown) => {
            setError(reason instanceof Error ? reason.message : "Radni prostor znanja nije mogao da se učita.");
          });
        }}
      />
    );
  }

  return (
    <>
      {inlineError ? <div className="error-panel wide-card">{inlineError}</div> : null}
      <SupportPageDeck
        eyebrow="Znanje"
        title="Izvori, režim i odgovor"
        summary="Najprirodniji redosled je da prvo proveriš izvore, zatim izabereš režim dokumenata ili veba i tek onda postaviš pitanje."
        steps={[
          {
            title: "Dodaj ili proveri izvore",
            detail: "Prvo potvrdi da su folderi i fajlovi stvarno ušli u prostor znanja i da indeks ima šta da koristi.",
          },
          {
            title: "Izaberi režim dokumenata ili veba",
            detail: "Samo dokumenti je najčistiji izbor, Dokumenti + veb su najpraktičniji, a Samo veb služi kada želiš samo veb sloj.",
          },
          {
            title: "Pokreni upit ili odgovor",
            detail: "Upit vraća reference i dokumente, a Odgovor koristi iste izvore da napravi konačan lokalni odgovor.",
          },
        ]}
        actions={
          <button type="button" className="secondary-button" onClick={onOpenSearch}>
            Otvori Pretragu
          </button>
        }
        resultHint={
          <>
            <span className="status-label">Gde vidiš rezultat</span>
            <strong className="status-value">Izvori, indeks i odgovor su odmah ispod</strong>
            <p className="helper-text">
              Posle dodavanja izvora ili pokretanja upita, ista strana odmah pokazuje status
              indeksiranja, reference i konačan odgovor.
            </p>
          </>
        }
      />
      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Radni prostor znanja</span>
        <strong className="status-value">Lokalni dokumenti + opcioni veb kontekst</strong>
        <p className="helper-text">
          Ovaj tab indeksira lokalne fajlove installer-managed putem i omogućava tokove Samo
          dokumenti, Dokumenti + veb i Samo veb. Kada ti treba samo veb sloj, možeš i direktno da
          otvoriš tab Pretraga.
        </p>
        {currentWorkflowPreset ? (
          <p className="helper-text">
            Preset radnog toka: {currentWorkflowPreset.label} | {currentWorkflowPreset.summary}
          </p>
        ) : null}
        <div className="summary-metrics">
          <span>Izvori: {summary.sourceCount}</span>
          <span>Dokumenti: {summary.documentCount}</span>
          <span>Indeksirano: {summary.indexedDocumentCount}</span>
          <span>Greške: {summary.errorCount}</span>
        </div>
        <p className="helper-text">Podržani formati: {extensionLine}</p>
        <p className="helper-text">{summary.reindexStatus.summary}</p>
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Izvori</span>
        <div className="settings-page-grid knowledge-form-grid">
          <label className="settings-compact-field">
            <span>Kolekcija</span>
            <input
              type="text"
              value={sourceCollection}
              onChange={(event) => setSourceCollection(event.target.value)}
              placeholder="Priručnici, Beleške, Projekti..."
            />
          </label>
          <label className="settings-compact-field settings-medium-field">
            <span>Oznake</span>
            <input
              type="text"
              value={sourceTags}
              onChange={(event) => setSourceTags(event.target.value)}
              placeholder="gpu, llama, kodiranje"
            />
          </label>
        </div>
        <div className="settings-action-row knowledge-action-row">
          <input
            className="settings-path-input"
            placeholder="Unesi lokalnu putanju do fajla ili foldera"
            value={sourcePath}
            onChange={(event) => setSourcePath(event.target.value)}
          />
          <button
            type="button"
            className="secondary-button"
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
                setError(reason instanceof Error ? reason.message : "Birač foldera za znanje nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "browse" ? "Otvaram..." : "Pregledaj"}
          </button>
          <button
            type="button"
            className="action-button"
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
                  throw new Error(result.summary || "Izvor znanja nije dodat.");
                }
                setSourcePath("");
                setSourceCollection("");
                setSourceTags("");
                await refreshAfterAction();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Izvor znanja nije dodat.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "add" ? "Dodajem..." : "Dodaj izvor"}
          </button>
          <button
            type="button"
            className="action-button"
            disabled={busyAction === "reindex" || summary.sourceCount === 0}
            onClick={async () => {
              setBusyAction("reindex");
              setError(null);
              try {
                const result = await reindexKnowledge();
                if (result.status !== "ok") {
                  throw new Error(result.summary || "Ponovno indeksiranje znanja nije uspelo.");
                }
                await refreshAfterAction();
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Ponovno indeksiranje znanja nije uspelo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "reindex" ? "Ponovo indeksiram..." : "Ponovo indeksiraj"}
          </button>
          <button type="button" className="secondary-button" onClick={onOpenSearch}>
            Otvori pretragu
          </button>
        </div>
        {summary.sources.length ? (
          <div className="model-list">
            {summary.sources.map((item) => (
              <article className="model-item" key={item.id}>
                <div className="model-item-header">
                  <div className="model-item-copy">
                    <strong>{item.path}</strong>
                    <div className="muted-line">
                      {item.kind} | {item.exists ? "postoji" : "nedostaje"} | dokumenti: {item.documentCount} |
                      indeksirano: {item.indexedDocumentCount}
                    </div>
                    <div className="helper-text">
                      Kolekcija: {item.collection || "--"} | Oznake:{" "}
                      {item.tags.length ? item.tags.join(", ") : "--"}
                    </div>
                    <div className="helper-text">
                      Preskočeno: {item.skippedCount} | Greške: {item.errorCount} | Poslednje indeksiranje:{" "}
                      {item.lastIndexedAt || "--"}
                    </div>
                    {item.lastError ? <div className="helper-text">{item.lastError}</div> : null}
                  </div>
                  <button
                    type="button"
                    className="danger-button"
                    disabled={busyAction === item.id}
                    onClick={async () => {
                      setBusyAction(item.id);
                      setError(null);
                      try {
                        const result = await removeKnowledgeSource(item.id);
                        if (result.status !== "ok") {
                          throw new Error(result.summary || "Izvor znanja nije uklonjen.");
                        }
                        await refreshAfterAction();
                      } catch (reason: unknown) {
                        setError(reason instanceof Error ? reason.message : "Izvor znanja nije uklonjen.");
                      } finally {
                        setBusyAction("");
                      }
                    }}
                  >
                    Ukloni
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="helper-text">Još nema prijavljenih izvora znanja.</p>
        )}
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Upit i odgovor</span>
        <div className="settings-page-grid knowledge-form-grid">
          <label className="settings-compact-field">
            <span>Kolekcije</span>
            <CustomSelect
              value={collectionFilter}
              options={collectionOptions}
              onChange={setCollectionFilter}
              ariaLabel="Filtriraj kolekcije znanja"
            />
          </label>
          <label className="settings-compact-field">
            <span>Oznake</span>
            <CustomSelect
              value={tagFilter}
              options={tagOptions}
              onChange={setTagFilter}
              ariaLabel="Filtriraj oznake znanja"
            />
          </label>
        </div>
        <div className="settings-action-row knowledge-action-row">
          <div className="settings-control-block">
            <CustomSelect
              value={mode}
              options={knowledgeModeOptions}
              onChange={(value) => setMode(value as KnowledgeMode)}
              ariaLabel="Izaberi režim znanja"
            />
          </div>
          <input
            className="settings-path-input"
            placeholder={
              currentWorkflowPreset?.knowledgeDefaults.queryHint ||
              "Upiši pitanje za pretragu ili odgovor iz znanja"
            }
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="button"
            className="action-button"
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
                setError(reason instanceof Error ? reason.message : "Upit nad znanjem nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "query" ? "Pretražujem..." : "Pretraži dokumente"}
          </button>
          <button
            type="button"
            className="action-button"
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
                setError(reason instanceof Error ? reason.message : "Odgovor iz znanja nije uspeo.");
              } finally {
                setBusyAction("");
              }
            }}
          >
            {busyAction === "answer" ? "Odgovaram..." : `Odgovori (${renderModeLabel(mode)})`}
          </button>
        </div>
        <p className="helper-text">
          Samo dokumenti koristi samo lokalni indeks. Dokumenti + veb spaja lokalne dokumente sa
          istim zajedničkim SearxNG slojem koji koristi tab Pretraga. Samo veb ovde ostaje samo
          zgodan prelaz ka istom toku veb odgovora preko lokalnog modela.
        </p>
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Rezultati dokumenata</span>
        <strong className="status-value">{queryPayload?.summary || "Još nema rezultata dokumenata."}</strong>
        {queryPayload?.results?.length ? (
          <div className="model-list">
            {queryPayload.results.map((item) => (
              <article className="model-item" key={`${item.docId}-${item.path}`}>
                <div className="model-item-header">
                  <div className="model-item-copy">
                    <strong>{item.name}</strong>
                    <div className="muted-line">
                      {item.fileType} | skor: {item.score.toFixed(2)} | karaktera: {item.charCount}
                    </div>
                    <div className="muted-line">
                      Kolekcija: {item.collection || "--"} | Oznake:{" "}
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
          <p className="helper-text">Kad pokreneš upit nad znanjem, ovde će se pojaviti lokalni pogoci iz dokumenata.</p>
        )}
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Odgovor iz znanja</span>
        <strong className="status-value">{answerPayload?.answer || "Još nema odgovora iz znanja."}</strong>
        <div className="summary-metrics">
          <span>Režim: {answerPayload ? renderModeLabel(answerPayload.mode as KnowledgeMode) : "--"}</span>
          <span>Runtime: {answerPayload?.answerRuntime || "--"}</span>
          <span>Model: {answerPayload?.answerModel || "--"}</span>
          <span>Dokumenti: {answerPayload?.documentResultCount ?? 0}</span>
          <span>Veb: {answerPayload?.webResultCount ?? 0}</span>
          <span>Prompt tokens: {formatUsage(answerPayload?.usage?.promptTokens)}</span>
        </div>
        {answerPayload ? (
          <>
            <p className="helper-text">
              Kolekcije: {answerPayload.usedCollections.length ? answerPayload.usedCollections.join(", ") : "--"} |
              Oznake: {answerPayload.usedTags.length ? answerPayload.usedTags.join(", ") : "--"}
            </p>
            <div className="inline-actions knowledge-export-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  triggerDownload(
                    "knowledge-answer.json",
                    JSON.stringify(answerPayload, null, 2),
                    "application/json",
                  )
                }
              >
                Izvezi JSON
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  triggerDownload(
                    "knowledge-answer.md",
                    [
                      `# Odgovor iz znanja\n\n`,
                      `Upit: ${answerPayload.query}\n\n`,
                      `Režim: ${answerPayload.mode}\n\n`,
                      `${answerPayload.answer}\n\n`,
                      `## Citati\n`,
                      ...answerPayload.citations.map(
                        (citation) =>
                          `- [${citation.index}] ${citation.name} | ${citation.collection || "--"} | ${citation.path}\n`,
                      ),
                    ].join(""),
                    "text/markdown",
                  )
                }
              >
                Izvezi Markdown
              </button>
            </div>
          </>
        ) : null}
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Citati</span>
        {answerPayload?.citations?.length ? (
          <div className="model-list">
            {answerPayload.citations.map((citation) => (
              <article className="model-item" key={`${citation.index}-${citation.path}`}>
                <div className="model-item-header">
                  <div className="model-item-copy">
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
            Kad knowledge answer koristi lokalne dokumente, ovde ćeš videti koji dokumenti su korišćeni
            i njihove citate.
          </p>
        )}
      </section>

      <section className="status-card wide-card runtimepilot-faceplate-module knowledge-panel">
        <span className="status-label">Skorašnja istorija znanja</span>
        {summary.history.length ? (
          <div className="model-list">
            {summary.history.map((item) => (
              <article className="model-item" key={`${item.askedAt}-${item.query}`}>
                <div className="model-item-header">
                  <div className="model-item-copy">
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
          <p className="helper-text">Upiti i odgovori iz znanja upisuju se ovde kao lokalna istorija.</p>
        )}
      </section>
    </>
  );
}
