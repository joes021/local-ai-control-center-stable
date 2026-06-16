import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { applyCompatibilityAction, checkModelCompatibility } from "../lib/api";
import type {
  ActionResult,
  BrowserCompatibilityPayload,
  CompatibilityAction,
  CompatibilityCheckRequest,
} from "../lib/types";
import { ActionResultPanel } from "./ActionResultPanel";
import { CustomSelect } from "./CustomSelect";
import { RuntimePilotIcon } from "./RuntimePilotIcon";

type Props = {
  title: string;
  request: CompatibilityCheckRequest | null;
  onClose?: () => void;
  headerActions?: ReactNode;
  emptyState?: ReactNode;
  className?: string;
  onPayloadChange?: (payload: BrowserCompatibilityPayload | null) => void;
};

function formatGiB(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(1)} GiB`;
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${Math.round(value)}%`;
}

function formatHeadroom(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} GiB`;
}

function formatInteger(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return value.toLocaleString("sr-RS");
}

function runtimeLabel(value: string | null | undefined) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "turboquant") {
    return "TurboQuant";
  }
  if (normalized === "llama.cpp") {
    return "llama.cpp";
  }
  return value || "--";
}

function fitBadgeClass(fitStatus: string) {
  if (fitStatus === "radi") {
    return "compat-badge compat-badge-ok";
  }
  if (fitStatus === "granicno") {
    return "compat-badge compat-badge-warn";
  }
  if (fitStatus === "ne radi") {
    return "compat-badge compat-badge-error";
  }
  return "compat-badge";
}

function speedBadgeClass(speedStatus: string | undefined) {
  if (speedStatus === "faster") {
    return "compat-badge compat-badge-ok";
  }
  if (speedStatus === "slower" || speedStatus === "much-slower") {
    return "compat-badge compat-badge-warn";
  }
  return "compat-badge";
}

function barStyle(percent: number | null | undefined) {
  const safePercent =
    percent === null || percent === undefined || Number.isNaN(percent)
      ? 0
      : Math.max(0, Math.min(100, percent));
  return { width: `${safePercent}%` };
}

export function CompatibilityCalculatorPanel({
  title,
  request,
  onClose,
  headerActions,
  emptyState,
  className,
  onPayloadChange,
}: Props) {
  const [payload, setPayload] = useState<BrowserCompatibilityPayload | null>(null);
  const [pending, setPending] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [overrides, setOverrides] = useState<CompatibilityCheckRequest["overrides"]>(
    {
      context: 32768,
      outputTokens: 2048,
      ctk: "turbo4",
      ctv: "turbo3",
      ncmoe: 20,
      runtimePreference: "turboquant",
    },
  );

  useEffect(() => {
    if (!request) {
      setPayload(null);
      setResult(null);
      onPayloadChange?.(null);
      return;
    }

    let cancelled = false;
    setPending(true);
    setPayload(null);
    setResult(null);

    void checkModelCompatibility({ ...request, overrides })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setPayload(response);
        onPayloadChange?.(response);
        const snapshot = response.systemSnapshot;
        if (snapshot) {
          setOverrides({
            ramGiB: snapshot.ramGiB,
            vramGiB: snapshot.vramGiB,
            context: snapshot.context,
            outputTokens: snapshot.outputTokens,
            turboQuantAvailable: snapshot.turboQuantAvailable,
            ctk: snapshot.turboQuantConfig?.ctk ?? "turbo4",
            ctv: snapshot.turboQuantConfig?.ctv ?? "turbo3",
            ncmoe: snapshot.turboQuantConfig?.ncmoe ?? 20,
            runtimePreference:
              snapshot.turboQuantConfig?.runtimePreference ?? "turboquant",
          });
        }
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          const message =
            reason instanceof Error
              ? reason.message
              : "Compatibility provera nije uspela.";
          setResult({
            status: "error",
            action: "compatibility-check",
            summary: message,
            details: { returncode: 1, stdout: "", stderr: message },
          });
          onPayloadChange?.(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPending(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [request]);

  const quantOptions = useMemo(
    () => [
      { value: "turbo4", label: "turbo4" },
      { value: "turbo3", label: "turbo3" },
      { value: "turbo2", label: "turbo2" },
      { value: "q8_0", label: "q8_0" },
      { value: "f16", label: "f16" },
    ],
    [],
  );

  const runtimeOptions = useMemo(
    () => [
      { value: "turboquant", label: "TurboQuant" },
      { value: "llama.cpp", label: "llama.cpp" },
    ],
    [],
  );

  const liveSnapshot = payload?.systemSnapshot ?? null;
  const liveTurbo = liveSnapshot?.turboQuantConfig ?? null;
  const editorDiffs = useMemo(
    () => [
      {
        id: "context",
        label: "Context",
        active: formatInteger(liveSnapshot?.context ?? null),
        editor: formatInteger(overrides?.context ?? null),
      },
      {
        id: "output",
        label: "Output",
        active: formatInteger(liveSnapshot?.outputTokens ?? null),
        editor: formatInteger(overrides?.outputTokens ?? null),
      },
      {
        id: "ctk-ctv",
        label: "ctk / ctv",
        active: liveTurbo ? `${liveTurbo.ctk} / ${liveTurbo.ctv}` : "--",
        editor: `${overrides?.ctk ?? "turbo4"} / ${overrides?.ctv ?? "turbo3"}`,
      },
      {
        id: "ncmoe",
        label: "ncmoe",
        active: formatInteger(liveTurbo?.ncmoe ?? null),
        editor: formatInteger(overrides?.ncmoe ?? null),
      },
      {
        id: "runtime",
        label: "Runtime",
        active: runtimeLabel(liveTurbo?.runtimePreference ?? null),
        editor: runtimeLabel(overrides?.runtimePreference ?? null),
      },
    ],
    [liveSnapshot?.context, liveSnapshot?.outputTokens, liveTurbo, overrides],
  );
  const changedEditorCount = useMemo(
    () => editorDiffs.filter((item) => item.active !== item.editor).length,
    [editorDiffs],
  );
  const lastActionSummary =
    result?.summary ||
    "Još nema nove akcije. Posle provere ili primene potvrda se pojavljuje ovde i u aktivnom stanju ispod.";

  async function handleRecheck(
    nextOverrides?: CompatibilityCheckRequest["overrides"],
  ) {
    if (!request) {
      return;
    }
    setPending(true);
    try {
      const response = await checkModelCompatibility({
        ...request,
        overrides: nextOverrides ?? overrides,
      });
      setPayload(response);
      setResult({
        status: "ok",
        action: "compatibility-check",
        summary:
          "Kompatibilnost je osvežena sa trenutnim editor vrednostima. Aktivno stanje i fit su ažurirani ispod.",
        details: {
          returncode: 0,
          stdout: "Compatibility rezultat i aktivni runtime fit su osveženi.",
          stderr: "",
        },
      });
      onPayloadChange?.(response);
    } catch (reason: unknown) {
      const message =
        reason instanceof Error
          ? reason.message
          : "Compatibility provera nije uspela.";
      setResult({
        status: "error",
        action: "compatibility-check",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
      onPayloadChange?.(null);
    } finally {
      setPending(false);
    }
  }

  async function handleApply(action: CompatibilityAction) {
    if (!request) {
      return;
    }
    if (
      action.requiresConfirmation &&
      !window.confirm(
        "Ova akcija menja više važnih podešavanja. Nastaviti?",
      )
    ) {
      return;
    }
    setPending(true);
    try {
      const response = await applyCompatibilityAction({
        catalogModelId: request.catalogModelId,
        model: request.model,
        overrides,
        action,
      });
      setPayload(response.compatibility);
      setResult(response.result);
      onPayloadChange?.(response.compatibility);
    } catch (reason: unknown) {
      const message =
        reason instanceof Error
          ? reason.message
          : "Compatibility apply nije uspeo.";
      setResult({
        status: "error",
        action: "compatibility-apply",
        summary: message,
        details: { returncode: 1, stdout: "", stderr: message },
      });
      onPayloadChange?.(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <section
      className={[
        "compatibility-calculator-panel",
        "runtimepilot-faceplate-module",
        "compat-rack-module",
        className || "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="section-header">
        <div>
          <span className="status-label">Kalkulator kompatibilnosti</span>
          <strong className="status-value">{title}</strong>
        </div>
        <div className="inline-actions compact-actions">
          {headerActions}
          {onClose ? (
            <button
              type="button"
              className="secondary-button"
              onClick={onClose}
            >
              Zatvori
            </button>
          ) : null}
        </div>
      </div>

      {!request ? (
        emptyState ?? (
          <div className="helper-text">
            Izaberi model da bi kalkulator kompatibilnosti mogao da radi proveru.
          </div>
        )
      ) : null}

      {pending && !payload && request ? (
        <div className="helper-text">Računam kompatibilnost...</div>
      ) : null}

      {payload ? (
        <>
          <div className="compatibility-monitor-deck">
          <div className="compat-header">
            <span className={fitBadgeClass(payload.fitStatus)}>
              {payload.fitLabel}
            </span>
            <span className={speedBadgeClass(payload.speedStatus)}>
              {payload.speedLabel ?? "Slično"}
            </span>
          </div>
          <p className="helper-text">{payload.summary}</p>

          <section className="compat-section">
            <span className="status-label">Najbolji runtime</span>
            <div className="compat-budget-grid">
              <div className="compat-budget-card">
                <strong className="status-value">
                  {payload.bestRuntimeLabel ?? "llama.cpp"}
                </strong>
                <div className="helper-text">
                  Ukupni fit: {payload.overallFitLabel ?? payload.fitLabel}
                </div>
              </div>
            </div>
          </section>

          {payload.runtimeBreakdown ? (
            <section className="compat-section">
              <span className="status-label">Pregled po runtime-u</span>
              <div className="compat-budget-grid">
                {Object.values(payload.runtimeBreakdown).map((runtime) => (
                  <div className="compat-budget-card" key={runtime.runtime}>
                    <div className="compat-header">
                      <strong className="status-value">
                        {runtime.runtimeLabel}
                      </strong>
                      <span className={fitBadgeClass(runtime.fitStatus)}>
                        {runtime.fitLabel}
                      </span>
                    </div>
                    <div className="helper-text">{runtime.summary}</div>
                    <div className="summary-metrics">
                      <span>{runtime.speedLabel ?? "Slično"}</span>
                      <span>
                        {runtime.estimated?.contextPressureLabel ?? "--"} kontekst
                      </span>
                      <span>
                        {runtime.estimated?.outputPressureLabel ?? "--"} izlaz
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="compat-budget-grid">
            <div className="compat-budget-card">
              <span className="status-label">VRAM</span>
              <strong className="status-value">
                {formatGiB(payload.memoryBudget?.vram.requiredGiB)} /{" "}
                {formatGiB(payload.memoryBudget?.vram.availableGiB)}
              </strong>
              <div className="compat-bar">
                <div
                  className="compat-bar-fill compat-bar-fill-vram"
                  style={barStyle(payload.memoryBudget?.vram.usagePercent)}
                />
              </div>
              <div className="helper-text">
                {formatPercent(payload.memoryBudget?.vram.usagePercent)} |{" "}
                Rezerva memorije{" "}
                {formatHeadroom(payload.memoryBudget?.vram.headroomGiB)}
              </div>
            </div>
            <div className="compat-budget-card">
              <span className="status-label">RAM</span>
              <strong className="status-value">
                {formatGiB(payload.memoryBudget?.ram.requiredGiB)} /{" "}
                {formatGiB(payload.memoryBudget?.ram.availableGiB)}
              </strong>
              <div className="compat-bar">
                <div
                  className="compat-bar-fill compat-bar-fill-ram"
                  style={barStyle(payload.memoryBudget?.ram.usagePercent)}
                />
              </div>
              <div className="helper-text">
                {formatPercent(payload.memoryBudget?.ram.usagePercent)} |{" "}
                Rezerva memorije{" "}
                {formatHeadroom(payload.memoryBudget?.ram.headroomGiB)}
              </div>
            </div>
            <div className="compat-budget-card">
              <span className="status-label">Opterećenje konteksta</span>
              <strong className="status-value">
                {payload.memoryBudget?.contextPressure.label}
              </strong>
              <div className="compat-bar">
                <div
                  className="compat-bar-fill compat-bar-fill-context"
                  style={barStyle(
                    payload.memoryBudget?.contextPressure.usagePercent,
                  )}
                />
              </div>
              <div className="helper-text">
                {payload.memoryBudget?.contextPressure.currentContext ?? "--"} |
                kapacitet{" "}
                {payload.memoryBudget?.contextPressure.effectiveCapacity ?? "--"}
              </div>
            </div>
            <div className="compat-budget-card">
              <span className="status-label">Opterećenje izlaza</span>
              <strong className="status-value">
                {payload.memoryBudget?.outputPressure?.label ?? "--"}
              </strong>
              <div className="compat-bar">
                <div
                  className="compat-bar-fill compat-bar-fill-context"
                  style={barStyle(
                    payload.memoryBudget?.outputPressure?.usagePercent,
                  )}
                />
              </div>
              <div className="helper-text">
                {payload.memoryBudget?.outputPressure?.currentOutputTokens ??
                  "--"}{" "}
                | default{" "}
                {payload.memoryBudget?.outputPressure?.defaultOutputTokens ??
                  "--"}
              </div>
            </div>
          </section>
          </div>

          <div className="compatibility-transport-deck">
            <section className="compat-section">
              <div className="section-header">
                <span className="status-label">Provera i primena</span>
                <div className="inline-actions compact-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={pending}
                    onClick={() => void handleRecheck()}
                  >
                    Proveri ponovo
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => setAdvancedOpen((current) => !current)}
                  >
                    {advancedOpen ? "Sakrij napredno" : "Prikaži napredno"}
                  </button>
                </div>
              </div>
              <div className="compatibility-action-route-grid">
                <article className="compatibility-action-route-card runtimepilot-readout-card">
                  <span className="status-label">Proveri ponovo</span>
                  <strong className="status-value">Fit, budžet i preporuke gore</strong>
                  <p className="helper-text">
                    Ovaj klik osvežava kalkulator, pa rezultat prvo čitaš u gornjim fit i budžet
                    karticama.
                  </p>
                </article>
                <article className="compatibility-action-route-card runtimepilot-readout-card">
                  <span className="status-label">Primeni</span>
                  <strong className="status-value">Aktivno sada na runtime-u</strong>
                  <p className="helper-text">
                    Kad klikneš Primeni, prvo gledaj Aktivno sada na runtime-u.
                  </p>
                </article>
                <article className="compatibility-action-route-card runtimepilot-readout-card">
                  <span className="status-label">Napredna izmena</span>
                  <strong className="status-value">Editor čeka proveru</strong>
                  <p className="helper-text">
                    Napredne izmene menjaju samo editor. Tek posle Proveri ili Primeni poredi ih sa
                    aktivnim stanjem.
                  </p>
                </article>
              </div>
              <div className="apply-state-panel compatibility-apply-state-panel">
                <article className="apply-state-chip runtimepilot-state-chip">
                  <span className="apply-state-chip-title">Editor čeka proveru</span>
                  <strong className="apply-state-chip-value">
                    {changedEditorCount
                      ? `${changedEditorCount} polja se razlikuju od aktivnog stanja`
                      : "Editor je usklađen sa aktivnim stanjem"}
                  </strong>
                </article>
                <article className="apply-state-chip runtimepilot-state-chip">
                  <span className="apply-state-chip-title">Aktivno sada</span>
                  <strong className="apply-state-chip-value">
                    {runtimeLabel(liveTurbo?.runtimePreference ?? null)} | ctx{" "}
                    {formatInteger(liveSnapshot?.context ?? null)}
                  </strong>
                </article>
                <article className="apply-state-chip runtimepilot-state-chip">
                  <span className="apply-state-chip-title">Poslednja akcija</span>
                  <strong className="apply-state-chip-value">{lastActionSummary}</strong>
                </article>
              </div>
              <section className="compatibility-live-settings-panel runtimepilot-faceplate-module">
                <div className="compatibility-live-settings-heading">
                  <span className="runtimepilot-section-glyph">
                    <RuntimePilotIcon
                      className="runtimepilot-section-glyph-icon"
                      name="observability"
                    />
                  </span>
                  <div>
                    <span className="status-label">Aktivno sada na runtime-u</span>
                    <strong className="status-value">
                      Ovo su vrednosti koje su trenutno važeće, ne samo one iz editora.
                    </strong>
                  </div>
                </div>
                <div className="compatibility-live-settings-grid">
                  <article className="compatibility-live-setting-card runtimepilot-readout-card">
                    <span className="status-label">Context</span>
                    <strong className="status-value">
                      {formatInteger(liveSnapshot?.context ?? null)}
                    </strong>
                  </article>
                  <article className="compatibility-live-setting-card runtimepilot-readout-card">
                    <span className="status-label">Output</span>
                    <strong className="status-value">
                      {formatInteger(liveSnapshot?.outputTokens ?? null)}
                    </strong>
                  </article>
                  <article className="compatibility-live-setting-card runtimepilot-readout-card">
                    <span className="status-label">ctk / ctv</span>
                    <strong className="status-value">
                      {liveTurbo ? `${liveTurbo.ctk} / ${liveTurbo.ctv}` : "--"}
                    </strong>
                  </article>
                  <article className="compatibility-live-setting-card runtimepilot-readout-card">
                    <span className="status-label">ncmoe</span>
                    <strong className="status-value">
                      {formatInteger(liveTurbo?.ncmoe ?? null)}
                    </strong>
                  </article>
                  <article className="compatibility-live-setting-card runtimepilot-readout-card">
                    <span className="status-label">Runtime</span>
                    <strong className="status-value">
                      {runtimeLabel(liveTurbo?.runtimePreference ?? null)}
                    </strong>
                  </article>
                </div>
                <p className="helper-text">
                  Proveri ili primeni da bi aktivno stanje ispod bilo ažurirano. Kad klikneš
                  Primeni, prvo gledaj ove vrednosti. Ako brojevi ostanu isti, akcija još nije
                  stigla do živog runtime-a.
                </p>
              </section>
              {payload.recommendations?.length ? (
                <div className="compat-recommendation-list">
                  {payload.recommendations.map((item) => (
                    <div className="compat-recommendation" key={item.id}>
                      <div className="compat-recommendation-copy">
                        <strong>{item.title}</strong>
                        <div className="helper-text">{item.summary}</div>
                        <div className="muted-line">{item.tradeoff}</div>
                      </div>
                      {item.action ? (
                        <button
                          type="button"
                          className="action-button"
                          disabled={pending}
                          onClick={() => void handleApply(item.action!)}
                        >
                          {item.action.kind === "apply-package"
                            ? "Primeni paket"
                            : "Primeni"}
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="helper-text">
                  Trenutni izbor nema gotov paket za primenu, ali možeš odmah da ponoviš proveru
                  ili da otvoriš napredne izmene ispod.
                </p>
              )}
              <div className="compatibility-action-result-inline">
                <ActionResultPanel result={result} />
              </div>
            </section>

          {advancedOpen ? (
            <section className="compat-section compatibility-editor-settings-panel runtimepilot-faceplate-module">
              <div className="compatibility-live-settings-heading">
                <span className="runtimepilot-section-glyph">
                  <RuntimePilotIcon
                    className="runtimepilot-section-glyph-icon"
                    name="settings"
                  />
                </span>
                <div>
                  <span className="status-label">Napredna izmena</span>
                  <strong className="status-value">
                    Napredna izmena menja editor, ne živi runtime
                  </strong>
                </div>
              </div>
              <p className="helper-text">
                Ovde menjaš radne vrednosti za sledeću proveru ili primenu. Tek posle Proveri ili
                Primeni aktivno stanje iznad treba da se promeni.
              </p>
              <div className="compat-advanced-grid">
                <label className="browser-field compat-advanced-control">
                  <span>Kontekst</span>
                  <input
                    type="number"
                    value={overrides?.context ?? 32768}
                    onChange={(event) =>
                      setOverrides((current) => ({
                        ...current,
                        context: Number(event.target.value) || 0,
                      }))
                    }
                  />
                </label>
                <label className="browser-field compat-advanced-control">
                  <span>Izlaz</span>
                  <input
                    type="number"
                    value={overrides?.outputTokens ?? 2048}
                    onChange={(event) =>
                      setOverrides((current) => ({
                        ...current,
                        outputTokens: Number(event.target.value) || 0,
                      }))
                    }
                  />
                </label>
                <label className="browser-field compat-advanced-control">
                  <span>ctk</span>
                  <CustomSelect
                    value={overrides?.ctk ?? "turbo4"}
                    options={quantOptions}
                    onChange={(value) =>
                      setOverrides((current) => ({ ...current, ctk: value }))
                    }
                    ariaLabel="Compatibility ctk"
                  />
                </label>
                <label className="browser-field compat-advanced-control">
                  <span>ctv</span>
                  <CustomSelect
                    value={overrides?.ctv ?? "turbo3"}
                    options={quantOptions}
                    onChange={(value) =>
                      setOverrides((current) => ({ ...current, ctv: value }))
                    }
                    ariaLabel="Compatibility ctv"
                  />
                </label>
                <label className="browser-field compat-advanced-control">
                  <span>ncmoe</span>
                  <input
                    type="number"
                    value={overrides?.ncmoe ?? 20}
                    onChange={(event) =>
                      setOverrides((current) => ({
                        ...current,
                        ncmoe: Number(event.target.value) || 0,
                      }))
                    }
                  />
                </label>
                <label className="browser-field compat-advanced-control">
                  <span>Runtime</span>
                  <CustomSelect
                    value={overrides?.runtimePreference ?? "turboquant"}
                    options={runtimeOptions}
                    onChange={(value) =>
                      setOverrides((current) => ({
                        ...current,
                        runtimePreference: value,
                      }))
                    }
                    ariaLabel="Compatibility runtime preference"
                  />
                </label>
              </div>
              <div className="compatibility-editor-diff-grid">
                {editorDiffs.map((item) => {
                  const changed = item.active !== item.editor;
                  return (
                    <article
                      className={`compatibility-editor-diff-card${
                        changed ? " compatibility-editor-diff-card-changed" : ""
                      }`}
                      key={item.id}
                    >
                      <span className="status-label">{item.label}</span>
                      <strong className="status-value">{item.editor}</strong>
                      <div className="helper-text">Aktivno: {item.active}</div>
                    </article>
                  );
                })}
              </div>
              <div className="inline-actions compact-actions">
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => void handleRecheck()}
                >
                  Proveri ponovo sa izmenama
                </button>
              </div>
            </section>
          ) : null}
          </div>

          <div className="compatibility-monitor-deck">
            <section className="compat-section">
              <div className="section-header">
                <span className="status-label">Razlozi</span>
                <span className="helper-text">
                  Ovde vidiš zašto je kalkulator doneo baš ovu preporuku.
                </span>
              </div>
              <div className="browser-reasoning-list">
                {Object.entries(payload.reasoning ?? {}).map(([key, value]) => (
                  <div className="muted-line" key={key}>
                    <strong>{key}:</strong> {value}
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
