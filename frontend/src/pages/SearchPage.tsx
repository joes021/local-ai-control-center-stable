import { useEffect, useMemo, useState } from "react";

import { CustomSelect } from "../components/CustomSelect";
import {
  answerWithLocalModel,
  bootstrapManagedSearchProvider,
  fetchSearchProviderStatus,
  fetchSearchSummary,
  runSearchQuery,
} from "../lib/api";
import type {
  SearchAnswerPayload,
  SearchProviderOption,
  SearchProviderStatusPayload,
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

function providerLabel(
  providerId: string,
  options: SearchProviderOption[],
) {
  return options.find((item) => item.id === providerId)?.label ?? providerId;
}

function renderResultsList(payload: SearchQueryPayload) {
  if (!payload.results.length) {
    return <p className="helper-text">Provider nije vratio rezultate za ovaj upit.</p>;
  }
  return (
    <div className="model-list">
      {payload.results.map((item) => (
        <article className="model-item" key={`${payload.provider}-${item.url}-${item.title}`}>
          <div className="model-item-header">
            <div>
              <strong>
                <a href={item.url} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
              </strong>
              <div className="muted-line">
                <a href={item.url} target="_blank" rel="noreferrer">
                  {item.url}
                </a>
              </div>
              <p className="helper-text">{item.snippet}</p>
              <div className="muted-line">
                Engine: {item.engine} | Provider: {payload.providerLabel} |{" "}
                <a href={item.url} target="_blank" rel="noreferrer">
                  Open source
                </a>
              </div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

type SearchPageProps = {
  onOpenSettings?: () => void;
};

export function SearchPage({ onOpenSettings }: SearchPageProps) {
  const [summary, setSummary] = useState<SearchSummaryPayload | null>(null);
  const [providerStatus, setProviderStatus] = useState<SearchProviderStatusPayload | null>(null);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [query, setQuery] = useState("");
  const [searchPayload, setSearchPayload] = useState<SearchQueryPayload | null>(null);
  const [comparePayloads, setComparePayloads] = useState<SearchQueryPayload[]>([]);
  const [answerPayload, setAnswerPayload] = useState<SearchAnswerPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [providerNotice, setProviderNotice] = useState<string | null>(null);
  const [providerBusy, setProviderBusy] = useState<"" | "check" | "setup">("");
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingAnswer, setLoadingAnswer] = useState(false);
  const [loadingCompare, setLoadingCompare] = useState(false);

  async function loadSummary() {
    const payload = await fetchSearchSummary();
    setSummary(payload);
    setProviderStatus(payload.providerStatus);
    setSelectedProvider((current) => current || payload.settings.provider);
  }

  async function refreshSelectedProviderStatus(providerId: string) {
    if (!summary) {
      return;
    }
    if (providerId === summary.settings.provider) {
      setProviderStatus(summary.providerStatus);
      return;
    }
    const nextStatus = await fetchSearchProviderStatus(providerId);
    setProviderStatus(nextStatus);
  }

  async function handleSearchOnly() {
    setLoadingSearch(true);
    setError(null);
    try {
      const payload = await runSearchQuery(query, { provider: selectedProvider });
      setSearchPayload(payload);
      setComparePayloads([]);
      setAnswerPayload(null);
      await loadSummary();
      await refreshSelectedProviderStatus(selectedProvider);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Web search nije uspeo.");
    } finally {
      setLoadingSearch(false);
    }
  }

  async function handleAnswer() {
    setLoadingAnswer(true);
    setError(null);
    try {
      const payload = await answerWithLocalModel(query, { provider: selectedProvider });
      setAnswerPayload(payload);
      setSearchPayload(payload);
      setComparePayloads([]);
      await loadSummary();
      await refreshSelectedProviderStatus(selectedProvider);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Lokalni odgovor nije uspeo.");
    } finally {
      setLoadingAnswer(false);
    }
  }

  async function handleCompare() {
    if (!summary) {
      return;
    }
    setLoadingCompare(true);
    setError(null);
    try {
      const providers = summary.availableProviders.map((item) => item.id);
      const payloads = await Promise.all(
        providers.map((providerId) => runSearchQuery(query, { provider: providerId })),
      );
      setComparePayloads(payloads);
      setSearchPayload(null);
      setAnswerPayload(null);
      await loadSummary();
      await refreshSelectedProviderStatus(selectedProvider);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Compare provider upit nije uspeo.");
    } finally {
      setLoadingCompare(false);
    }
  }

  useEffect(() => {
    void loadSummary().catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Search summary nije mogao da se ucita.");
    });
  }, []);

  useEffect(() => {
    if (!summary || !selectedProvider) {
      return;
    }
    void refreshSelectedProviderStatus(selectedProvider).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : "Provider status nije mogao da se ucita.");
    });
  }, [selectedProvider, summary]);

  const currentSettingsLine = useMemo(() => {
    if (!summary || !providerStatus) {
      return "";
    }
    return `Mode: ${renderSearchModeLabel(summary.settings.mode, summary.settings.promptPrefix)} | Default provider: ${providerLabel(summary.settings.provider, summary.availableProviders)} | Trenutni provider: ${providerLabel(selectedProvider || summary.settings.provider, summary.availableProviders)} | Aktivni endpoint: ${providerStatus.effectiveBaseUrl || "nije potreban"}`;
  }, [providerStatus, selectedProvider, summary]);

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!summary || !providerStatus) {
    return <section className="status-card wide-card">Ucitavam Search workspace...</section>;
  }

  const currentProviderOption =
    summary.availableProviders.find((item) => item.id === selectedProvider) ?? null;
  const isManagedSearxng = selectedProvider === "searxng";

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Search workspace</span>
        <strong className="status-value">Shared web search + lokalni model + OpenCode local-lacc</strong>
        <p className="helper-text">{currentSettingsLine}</p>
        <p className="helper-text">
          Ovaj tab koristi isti shared search sloj kao i OpenCode `local-lacc` provider. Cloud
          `opencode` modeli ne prolaze kroz ovaj lokalni proxy put.
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Search provider</span>
        <strong className="status-value">
          {providerLabel(selectedProvider, summary.availableProviders)}: {providerStatus.label}
        </strong>
        <p className="helper-text">{providerStatus.summary}</p>
        <div className="settings-action-row">
          <div className="settings-control-block settings-control-block-wide">
            <CustomSelect
              value={selectedProvider}
              options={summary.availableProviders.map((item) => ({
                value: item.id,
                label: item.label,
              }))}
              onChange={(value) => {
                setSelectedProvider(value);
                setProviderNotice(null);
              }}
              ariaLabel="Izaberi search provider"
            />
          </div>
          <button
            type="button"
            disabled={providerBusy !== ""}
            onClick={async () => {
              setProviderBusy("check");
              setError(null);
              try {
                const nextStatus = await fetchSearchProviderStatus(selectedProvider);
                setProviderStatus(nextStatus);
                setProviderNotice(nextStatus.summary);
              } catch (reason: unknown) {
                setError(reason instanceof Error ? reason.message : "Health check nije uspeo.");
              } finally {
                setProviderBusy("");
              }
            }}
          >
            {providerBusy === "check" ? "Checking..." : "Check health"}
          </button>
          {isManagedSearxng ? (
            <button
              type="button"
              disabled={providerBusy !== "" || providerStatus.canBootstrap === false}
              title={providerStatus.canBootstrap ? undefined : providerStatus.bootstrapSummary}
              onClick={async () => {
                setProviderBusy("setup");
                setError(null);
                try {
                  const payload = await bootstrapManagedSearchProvider(selectedProvider);
                  setProviderStatus(payload.providerStatus);
                  setProviderNotice(payload.result.summary);
                  await loadSummary();
                } catch (reason: unknown) {
                  setError(reason instanceof Error ? reason.message : "Managed SearxNG setup nije uspeo.");
                } finally {
                  setProviderBusy("");
                }
              }}
            >
              {providerBusy === "setup"
                ? "Setting up managed SearxNG..."
                : "Setup managed SearxNG (Windows + WSL)"}
            </button>
          ) : null}
          {onOpenSettings ? (
            <button type="button" className="secondary-button" onClick={onOpenSettings}>
              Open Search settings
            </button>
          ) : null}
        </div>
        <div className="summary-metrics">
          <span>Source: {providerStatus.source || "--"}</span>
          <span>Configured URL: {providerStatus.configuredBaseUrl || "--"}</span>
          <span>Effective URL: {providerStatus.effectiveBaseUrl || "--"}</span>
          <span>Service: {providerStatus.serviceLabel || "--"}</span>
        </div>
        {providerNotice ? <p className="helper-text">{providerNotice}</p> : null}
        {currentProviderOption ? <p className="helper-text">{currentProviderOption.summary}</p> : null}
        {isManagedSearxng ? (
          <>
            <p className="helper-text">
              Managed setup koristi WSL da lokalno podigne SearxNG. Ako ne zelis taj put, unesi rucni
              SearxNG URL u Settings.
            </p>
            <p className="helper-text">
              Ako provider status kaze `SearxNG nije podesen`, Search i local answer ostaju ugaseni dok
              ne podignes lokalni provider ili ne upises pravi endpoint.
            </p>
          </>
        ) : (
          <p className="helper-text">
            DuckDuckGo radi kao javni no-key provider. Ne koristi managed bootstrap i ne trazi WSL,
            ali je integracija best-effort i moze biti manje stabilna od SearxNG puta.
          </p>
        )}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Web query</span>
        <div className="settings-action-row">
          <input
            className="settings-path-input"
            placeholder="Upisi pitanje ili temu za web search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !loadingAnswer &&
                providerStatus.canQuery !== false &&
                query.trim()
              ) {
                event.preventDefault();
                void handleAnswer();
              }
            }}
          />
          <button
            type="button"
            disabled={loadingSearch || !query.trim() || providerStatus.canQuery === false}
            onClick={() => {
              void handleSearchOnly();
            }}
          >
            {loadingSearch ? "Searching..." : "Find web sources"}
          </button>
          <button
            type="button"
            disabled={loadingAnswer || !query.trim() || providerStatus.canQuery === false}
            onClick={() => {
              void handleAnswer();
            }}
          >
            {loadingAnswer ? "Answering..." : "Search + answer locally"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={loadingCompare || !query.trim()}
            onClick={() => {
              void handleCompare();
            }}
          >
            {loadingCompare ? "Comparing..." : "Compare providers"}
          </button>
        </div>
        <p className="helper-text">
          `Find web sources` vraca samo izvore. `Search + answer locally` prvo radi isti web
          search, pa onda salje rezultate kao dodatni context aktivnom lokalnom runtime-u i vraca
          finalan odgovor.
        </p>
        <p className="helper-text">
          `Compare providers` paralelno prikazuje kako isti upit izgleda kroz SearxNG i DuckDuckGo.
        </p>
        {providerStatus.canQuery === false ? (
          <p className="helper-text">
            Search akcije su trenutno ugasene dok provider nije zdrav. Ako hoces managed local
            provider, klikni `Setup managed SearxNG (Windows + WSL)`.
          </p>
        ) : null}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Web sources</span>
        <strong className="status-value">
          {searchPayload?.summary || (comparePayloads.length ? "Provider compare je spreman." : "Jos nema rezultata.")}
        </strong>
        {searchPayload?.results?.length && !answerPayload ? (
          <div className="inline-actions compact-actions">
            <p className="helper-text">
              Ovo su izvori, ne finalan odgovor. Klikni `Search + answer locally` da isti upit
              odmah prosledis lokalnom modelu.
            </p>
            <button
              type="button"
              disabled={loadingAnswer || !query.trim() || providerStatus.canQuery === false}
              onClick={() => {
                void handleAnswer();
              }}
            >
              {loadingAnswer ? "Answering..." : "Answer from these results"}
            </button>
          </div>
        ) : null}
        {comparePayloads.length ? (
          <div className="model-list">
            {comparePayloads.map((payload) => (
              <article className="model-item" key={`compare-${payload.provider}`}>
                <div className="model-item-header">
                  <div>
                    <strong>{payload.providerLabel}</strong>
                    <div className="muted-line">{payload.summary}</div>
                  </div>
                </div>
                {renderResultsList(payload)}
              </article>
            ))}
          </div>
        ) : searchPayload ? (
          renderResultsList(searchPayload)
        ) : (
          <p className="helper-text">Kad pokrenes query, ovde ce se pojaviti normalizovani web rezultati.</p>
        )}
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Final answer from local model</span>
        <strong className="status-value">
          {answerPayload?.answer ||
            "Jos nema finalnog odgovora. Koristi `Search + answer locally` za odgovor zasnovan na web izvorima."}
        </strong>
        <div className="summary-metrics">
          <span>Provider: {answerPayload?.providerLabel || providerLabel(selectedProvider, summary.availableProviders)}</span>
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
