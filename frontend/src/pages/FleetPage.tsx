import { useEffect, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  RuntimePilotActionDeck,
  type RuntimePilotActionDeckItem,
} from "../components/shell/RuntimePilotActionDeck";
import {
  RuntimePilotStatusDeck,
  type RuntimePilotStatusDeckItem,
} from "../components/shell/RuntimePilotStatusDeck";
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
      setError(reason instanceof Error ? reason.message : "Akcija flote nije uspela.");
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
        loadingText="Učitavam flotu..."
        onRetry={() => {
          setError(null);
          void load();
        }}
      />
    );
  }

  const healthyMachineCount = machines.filter((machine) => !machine.lastError).length;
  const fastestMachine =
    [...machines].sort(
      (left, right) =>
        (right.snapshot.liveNowTokensPerSecond ?? -1) -
        (left.snapshot.liveNowTokensPerSecond ?? -1),
    )[0] ?? null;
  const latestMachine =
    [...machines].sort((left, right) => {
      const leftTime = Date.parse(left.lastCheckedAt || "");
      const rightTime = Date.parse(right.lastCheckedAt || "");
      return (Number.isFinite(rightTime) ? rightTime : 0) - (Number.isFinite(leftTime) ? leftTime : 0);
    })[0] ?? null;

  const scrollToForm = () => {
    document.getElementById("fleet-machine-form")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  const scrollToCatalog = () => {
    document.getElementById("fleet-machine-catalog")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  const scrollToResult = () => {
    document.getElementById("fleet-action-result")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };

  const fleetStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "machines",
      label: "Mašine",
      value: `${summary.machineCount}`,
      detail: `Zdravih ${healthyMachineCount} | poslednje osvežavanje ${formatDateTime(summary.generatedAt)}`,
      action: "Broj poznatih instalacija",
      icon: "fleet",
      accent: "rgba(242, 184, 75, 0.36)",
    },
    {
      id: "fastest",
      label: "Najbrži signal",
      value: fastestMachine?.name ?? "Nema uzorka",
      detail: fastestMachine
        ? `${formatTok(fastestMachine.snapshot.liveNowTokensPerSecond)} | ${fastestMachine.snapshot.activeModel}`
        : "Dodaj mašinu i osveži snimak da vidiš throughput poređenje.",
      action: "Najviši live tok/s",
      icon: "benchmark",
      accent: "rgba(109, 172, 255, 0.34)",
    },
    {
      id: "runtime",
      label: "Runtime signal",
      value: fastestMachine?.snapshot.activeRuntime ?? "Nema signala",
      detail: fastestMachine?.snapshot.runtimeLiveStatus || "Još nema aktivne udaljene runtime potvrde.",
      action: "Udaljeni engine status",
      icon: "runtime",
      accent: "rgba(88, 222, 193, 0.34)",
    },
    {
      id: "latest-check",
      label: "Poslednja provera",
      value: latestMachine ? latestMachine.name : "Nema mašina",
      detail: latestMachine
        ? formatDateTime(latestMachine.lastCheckedAt)
        : "Još nema mašina koje su poslale snapshot.",
      action: "Najskoriji refresh",
      icon: "logs",
      accent: "rgba(205, 162, 255, 0.34)",
    },
    {
      id: "result",
      label: "Poslednja akcija",
      value: result?.status === "ok" ? "Akcija potvrđena" : "Čeka novu akciju",
      detail: result?.summary || "Panel ispod potvrđuje dodavanje, osvežavanje ili uklanjanje mašine.",
      action: "Skok na rezultat",
      icon: "control",
      accent: "rgba(255, 129, 177, 0.34)",
      onClick: scrollToResult,
    },
  ];

  const fleetActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "refresh-all",
      code: "SYNC",
      title: "Osveži sve",
      subtitle: "POVUCI NOVE SNAPSHOT-E",
      icon: "reload",
      tone: "primary",
      detail: "Osvežava celu flotu bez pojedinačnog klikanja po karticama.",
      onClick: () => void runMutation(() => refreshFleetMachine()),
    },
    {
      id: "jump-form",
      code: "ADD",
      title: "Skok na formu",
      subtitle: "DODAJ MAŠINU",
      icon: "fleet",
      detail: "Idi pravo na unos naziva i URL-a nove instalacije.",
      onClick: scrollToForm,
    },
    {
      id: "jump-catalog",
      code: "CAT",
      title: "Skok na katalog",
      subtitle: "LISTA MAŠINA",
      icon: "server",
      detail: "Vrati se direktno na katalog i uporedi snapshot-e.",
      onClick: scrollToCatalog,
    },
    {
      id: "jump-result",
      code: "LOG",
      title: "Skok na rezultat",
      subtitle: "POSLEDNJA AKCIJA",
      icon: "logs",
      detail: result?.summary || "Panel ispod pokazuje ishod zadnje akcije.",
      onClick: scrollToResult,
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}
      <PageFlowCard
        title="Tok flote"
        summary="Ovde prvo dodaš mašinu, zatim osvežiš njen snimak, pa tek onda koristiš udaljeni panel ili telemetrijske brojke za poređenje."
        steps={[
          {
            title: "Dodaj mašinu",
            detail: "Naziv i osnovni URL su dovoljni da RuntimePilot počne da prati udaljenu instalaciju.",
          },
          {
            title: "Osveži snimak",
            detail: "Tok flote ima smisla tek kada povuče runtime, model i tok telemetrije sa druge mašine.",
          },
          {
            title: "Otvori panel ili uporedi signal",
            detail: "Kada je snapshot zdrav, koristi ga za brzu procenu ili otvori puni udaljeni panel.",
          },
        ]}
      />
      <RuntimePilotStatusDeck
        eyebrow="Status dashboard"
        title="Mašine, snapshot i rezultat"
        helper="Pet kartica odmah pokazuje koliko mašina pratiš, gde je najjači signal, koji runtime je živ i šta je uradila poslednja akcija."
        items={fleetStatusItems}
      />
      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Osveži, dodaj ili skoči na pravo mesto"
        helper="Na vrhu ostaju samo stvarne akcije: povuci novi snapshot, idi na formu, vrati se na katalog ili pročitaj rezultat mutacije."
        items={fleetActionItems}
      />

      <section className="status-card wide-card runtimepilot-faceplate-module">
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
      </section>

      <section
        id="fleet-machine-form"
        className="status-card wide-card runtimepilot-faceplate-module"
      >
        <span className="status-label">Dodaj mašinu</span>
        <div className="settings-page-grid">
          <label className="settings-compact-field">
            <span>Naziv</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Radna stanica, laptop, GPU čvor..."
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
            className="action-button"
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

      <section
        id="fleet-machine-catalog"
        className="status-card wide-card runtimepilot-faceplate-module"
      >
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

      <div id="fleet-action-result">
        <ActionResultPanel result={result} />
      </div>
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
        <button type="button" className="secondary-button" onClick={onRefresh}>
          Osveži
        </button>
        <a
          className="secondary-button"
          href={machine.snapshot.uiUrl || `${machine.baseUrl}/`}
          target="_blank"
          rel="noreferrer"
        >
          Otvori panel
        </a>
        <button type="button" className="danger-button" onClick={onRemove}>
          Ukloni
        </button>
      </div>
    </article>
  );
}
