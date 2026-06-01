import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  addFleetMachine,
  fetchFleetSummary,
  refreshFleetMachine,
  removeFleetMachine,
} from "../lib/api";
import type { ActionResult, FleetMachine, FleetSummaryPayload } from "../lib/types";

const REFRESH_MS = 15000;

function formatDateTime(value: string) {
  if (!value) {
    return "--";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString("sr-RS");
}

function formatTok(value: number | null | undefined) {
  if (typeof value !== "number") {
    return "--";
  }
  return `${value.toFixed(1)} tok/s`;
}

export function FleetPage() {
  const [summary, setSummary] = useState<FleetSummaryPayload | null>(null);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

  async function load() {
    try {
      const payload = await fetchFleetSummary();
      setSummary(payload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Flota nije mogla da se učita.");
    }
  }

  async function runMutation(callback: () => Promise<{ status: string; summary: string }>) {
    try {
      const payload = await callback();
      setResult({
        status: payload.status,
        action: "fleet-action",
        summary: payload.summary,
        details: {
          returncode: payload.status === "ok" ? 0 : 1,
          stdout: payload.summary,
          stderr: payload.status === "ok" ? "" : payload.summary,
        },
      });
      await load();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Fleet akcija nije uspela.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    void load();
    const timer = window.setInterval(() => {
      if (!cancelled) {
        void load();
      }
    }, REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const machines = summary?.machines ?? [];

  if (!summary) {
    return (
      <PageDataStateCard
        error={error}
        loadingText="U\u010ditavam flotu..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
  }

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Fleet tok"
        summary="Ovde prvo doda\u0161 ma\u0161inu, zatim osve\u017ei\u0161 njen snapshot, pa tek onda koristi\u0161 udaljeni panel ili telemetry brojke za pore\u0111enje."
        steps={[
          {
            title: "Dodaj ma\u0161inu",
            detail: "Naziv i osnovni URL su dovoljni da RuntimePilot po\u010dne da prati udaljenu instalaciju.",
          },
          {
            title: "Osve\u017ei snapshot",
            detail: "Fleet ima smisla tek kada povu\u010de runtime, model i live signal sa druge ma\u0161ine.",
          },
          {
            title: "Otvori panel ili uporedi signal",
            detail: "Kada je snapshot zdrav, koristi ga za brzu procenu ili otvori puni udaljeni panel.",
          },
        ]}
      />

      <section className="status-card wide-card">
        <span className="status-label">Flota</span>
        <strong className="status-value">Udaljene mašine</strong>
        <p className="helper-text">
          Jedan pogled za više instalacija: verzija, runtime, model, tok tokena i link nazad na
          njihov panel.
        </p>
        <div className="summary-metrics">
          <span>Mašina: {summary?.machineCount ?? 0}</span>
          <span>Osveženo: {summary ? formatDateTime(summary.generatedAt) : "--"}</span>
        </div>
        <div className="inline-actions">
          <button type="button" onClick={() => void runMutation(() => refreshFleetMachine())}>
            Osveži sve
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Dodaj mašinu</span>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Naziv</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Workstation, Laptop, GPU čvor..."
            />
          </label>
          <label className="settings-compact-field settings-medium-field">
            <span>Osnovni URL</span>
            <input
              type="text"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="http://192.0.2.10:3210"
            />
          </label>
        </div>
        <div className="inline-actions">
          <button
            type="button"
            disabled={!name.trim() || !baseUrl.trim()}
            onClick={() =>
              void runMutation(async () => {
                const payload = await addFleetMachine({ name, baseUrl });
                if (payload.status === "ok") {
                  setName("");
                  setBaseUrl("");
                }
                return payload;
              })
            }
          >
            Dodaj mašinu
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Katalog mašina</span>
        {machines.length ? (
          <div className="model-list">
            {machines.map((machine) => (
              <FleetMachineCard
                key={machine.id}
                machine={machine}
                onRefresh={() => void runMutation(() => refreshFleetMachine(machine.id))}
                onRemove={() => void runMutation(() => removeFleetMachine(machine.id))}
              />
            ))}
          </div>
        ) : (
          <p className="helper-text">
            Još nema dodatih mašina. Dodaj drugu Windows instalaciju da bi pratio runtime stanje,
            benchmark i signal ažuriranja sa jednog mesta.
          </p>
        )}
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}

function FleetMachineCard({
  machine,
  onRefresh,
  onRemove,
}: {
  machine: FleetMachine;
  onRefresh: () => void;
  onRemove: () => void;
}) {
  return (
    <article className="model-item">
      <div className="model-item-header">
        <div>
          <strong>{machine.name}</strong>
          <div className="muted-line">{machine.baseUrl}</div>
        </div>
        <span className="warning-badge">
          {machine.snapshot.runtimeLiveStatus} | {machine.snapshot.activeRuntime}
        </span>
      </div>
      <p className="helper-text">
        Model: {machine.snapshot.activeModel} | Verzija: {machine.snapshot.version} | Uživo sada:{" "}
        {formatTok(machine.snapshot.liveNowTokensPerSecond)} | Tok: {machine.snapshot.flowStateLabel}
      </p>
      <p className="helper-text">
        Ulaz 24h: {machine.snapshot.input24h} | Izlaz 24h: {machine.snapshot.output24h} | Zadnja
        provera: {formatDateTime(machine.lastCheckedAt)}
      </p>
      <p className="helper-text">
        {machine.lastError || machine.snapshot.runtimeSummary || "Nema dodatne runtime poruke."}
      </p>
      <div className="inline-actions">
        <button type="button" onClick={onRefresh}>
          Osveži
        </button>
        <a
          className="nav-button"
          href={machine.snapshot.uiUrl || `${machine.baseUrl}/`}
          target="_blank"
          rel="noreferrer"
        >
          Otvori panel
        </a>
        <button type="button" onClick={onRemove}>
          Ukloni
        </button>
      </div>
    </article>
  );
}
