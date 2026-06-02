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
      setResult(null);
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
    <section className={className}>
      <div className="section-header">
        <div>
          <span className="status-label">Compatibility calculator</span>
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
            Izaberi model da bi compatibility kalkulator mogao da radi proveru.
          </div>
        )
      ) : null}

      {pending && !payload && request ? (
        <div className="helper-text">Računam kompatibilnost...</div>
      ) : null}

      {payload ? (
        <>
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

          {payload.recommendations?.length ? (
            <section className="compat-section">
              <div className="section-header">
                <span className="status-label">Preporuke</span>
                <button
                  type="button"
                  className="secondary-button"
                  disabled={pending}
                  onClick={() => void handleRecheck()}
                >
                  Proveri ponovo
                </button>
              </div>
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
            </section>
          ) : null}

          <section className="compat-section">
            <div className="section-header">
              <span className="status-label">Razlozi</span>
              <button
                type="button"
                className="secondary-button"
                onClick={() => setAdvancedOpen((current) => !current)}
              >
                {advancedOpen ? "Sakrij napredno" : "Prikaži napredno"}
              </button>
            </div>
            <div className="browser-reasoning-list">
              {Object.entries(payload.reasoning ?? {}).map(([key, value]) => (
                <div className="muted-line" key={key}>
                  <strong>{key}:</strong> {value}
                </div>
              ))}
            </div>
          </section>

          {advancedOpen ? (
            <section className="compat-section">
              <span className="status-label">Napredna izmena</span>
              <div className="compat-advanced-grid">
                <label className="browser-field">
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
                <label className="browser-field">
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
                <label className="browser-field">
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
                <label className="browser-field">
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
                <label className="browser-field">
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
                <label className="browser-field">
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
        </>
      ) : null}

      <ActionResultPanel result={result} />
    </section>
  );
}
