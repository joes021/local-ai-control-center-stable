import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { applySettings, fetchSettings } from "../lib/api";
import { resolveWorkflowPresets } from "../lib/workflowPresets";
import type { ActionResult, SettingsPayload } from "../lib/types";

export function WorkflowsPage({
  onOpenSearch,
  onOpenKnowledge,
  onOpenBenchmark,
}: {
  onOpenSearch: () => void;
  onOpenKnowledge: () => void;
  onOpenBenchmark: () => void;
}) {
  const [settingsPayload, setSettingsPayload] = useState<SettingsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyPresetId, setBusyPresetId] = useState("");
  const [result, setResult] = useState<ActionResult | null>(null);

  async function load() {
    try {
      const payload = await fetchSettings();
      setSettingsPayload(payload);
      setError(null);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "Radni prostor za radne tokove nije mogao da se učita.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const presets = useMemo(
    () => resolveWorkflowPresets(settingsPayload),
    [settingsPayload],
  );

  if (error) {
    return <div className="error-panel">{error}</div>;
  }

  if (!settingsPayload) {
    return <section className="status-card wide-card">Učitavam radni prostor za radne tokove...</section>;
  }

  return (
    <>
      <section className="status-card wide-card">
        <span className="status-label">Radni tokovi</span>
        <strong className="status-value">Radni prostor za radne tokove</strong>
        <p className="helper-text">
          Preset sloj za najčešće radne tokove. Jednim klikom biraš pravac za Pretragu, Znanje,
          Benchmark i radni profil bez lutanja kroz više tabova.
        </p>
      </section>

      <section className="status-card wide-card">
        <span className="status-label">Katalog preseta</span>
        <div className="workflow-preset-grid">
          {presets.map((preset) => {
            const isActive = settingsPayload.selectedWorkflowPresetId === preset.id;
            return (
              <article
                className={`theme-option-card ${isActive ? "theme-option-card-active" : ""}`}
                key={preset.id}
              >
                <strong className="theme-option-name">{preset.label}</strong>
                <p className="theme-option-copy">{preset.summary}</p>
                <div className="summary-metrics">
                  {preset.badges.map((badge) => (
                    <span key={`${preset.id}-${badge}`}>{badge}</span>
                  ))}
                </div>
                <p className="helper-text">
                  Pretraga: {preset.searchDefaults.provider} | Znanje: {preset.knowledgeDefaults.mode} |
                  Benchmark: {preset.benchmarkDefaults.runLabel}
                </p>
                <div className="inline-actions">
                  <button
                    type="button"
                    disabled={busyPresetId === preset.id}
                    onClick={async () => {
                      setBusyPresetId(preset.id);
                      try {
                        const payload: SettingsPayload = {
                          ...settingsPayload,
                          ...preset.settingsPatch,
                          workflowPresetId: preset.id,
                          selectedWorkflowPresetId: preset.id,
                        };
                        const action = await applySettings(payload);
                        setResult(action);
                        await load();
                      } catch (reason: unknown) {
                        setError(reason instanceof Error ? reason.message : "Aktivacija workflow preseta nije uspela.");
                      } finally {
                        setBusyPresetId("");
                      }
                    }}
                  >
                    Aktiviraj preset
                  </button>
                  <button type="button" onClick={onOpenSearch}>
                    Otvori pretragu
                  </button>
                  <button type="button" onClick={onOpenKnowledge}>
                    Otvori znanje
                  </button>
                  <button type="button" onClick={onOpenBenchmark}>
                    Otvori benchmark
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}
