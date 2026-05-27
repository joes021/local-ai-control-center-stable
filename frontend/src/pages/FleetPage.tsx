import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
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
      setError(reason instanceof Error ? reason.message : "Fleet nije mogao da se ucita.");
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

  return (
    <>
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="status-card wide-card">
        <span className="status-label">Fleet</span>
        <strong className="status-value">Remote machines</strong>
        <p className="helper-text">
          Jedan pogled za vise instalacija: verzija, runtime, model, token flow i link nazad na
          njihov panel.
        </p>
        <div className="summary-metrics">
          <span>Masina: {summary?.machineCount ?? 0}</span>
          <span>Osvezeno: {summary ? formatDateTime(summary.generatedAt) : "--"}</span>
        </div>
        <div className="inline-actions">
          <button type="button" onClick={() => void runMutation(() => refreshFleetMachine())}>
            Refresh all
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Add machine</span>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Label</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Workstation, Laptop, GPU node..."
            />
          </label>
          <label className="settings-compact-field settings-medium-field">
            <span>Base URL</span>
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
            Add machine
          </button>
        </div>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Remote catalog</span>
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
            Jos nema dodatih masina. Dodaj drugu Windows instalaciju da bi pratio runtime stanje,
            benchmark i update signal sa jednog mesta.
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
        Model: {machine.snapshot.activeModel} | Verzija: {machine.snapshot.version} | Live now:{" "}
        {formatTok(machine.snapshot.liveNowTokensPerSecond)} | Flow: {machine.snapshot.flowStateLabel}
      </p>
      <p className="helper-text">
        Input 24h: {machine.snapshot.input24h} | Output 24h: {machine.snapshot.output24h} | Zadnja
        provera: {formatDateTime(machine.lastCheckedAt)}
      </p>
      <p className="helper-text">
        {machine.lastError || machine.snapshot.runtimeSummary || "Nema dodatne runtime poruke."}
      </p>
      <div className="inline-actions">
        <button type="button" onClick={onRefresh}>
          Refresh
        </button>
        <a
          className="nav-button"
          href={machine.snapshot.uiUrl || `${machine.baseUrl}/`}
          target="_blank"
          rel="noreferrer"
        >
          Open panel
        </a>
        <button type="button" onClick={onRemove}>
          Remove
        </button>
      </div>
    </article>
  );
}
