import { CustomSelect } from "../CustomSelect";
import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";

type TuningLabSlotDisplayPanelProps = {
  slot: TuningLabSlot;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

const TUNING_LAB_TOKEN_PRESET_OPTIONS = [
  { value: "1024", label: "1k" },
  { value: "2048", label: "2k" },
  { value: "4096", label: "4k" },
  { value: "8192", label: "8k" },
  { value: "16384", label: "16k" },
  { value: "32768", label: "32k" },
  { value: "65536", label: "64k" },
  { value: "131072", label: "128k" },
  { value: "262144", label: "256k" },
  { value: "524288", label: "512k" },
  { value: "1048576", label: "1M" },
] as const;

function resolveTokenPresetChoice(value: number): string {
  const matched = TUNING_LAB_TOKEN_PRESET_OPTIONS.find((option) => Number(option.value) === value);
  return matched?.value ?? "";
}

function formatDeckValue(value: number) {
  if (!Number.isFinite(value)) {
    return "--";
  }
  const matched = TUNING_LAB_TOKEN_PRESET_OPTIONS.find((option) => Number(option.value) === value);
  if (matched) {
    return matched.label;
  }
  return new Intl.NumberFormat("sr-RS").format(value);
}

export function TuningLabSlotDisplayPanel({
  slot,
  onPatchSlot,
}: TuningLabSlotDisplayPanelProps) {
  const contextPresetChoice = resolveTokenPresetChoice(slot.settingsPatch.context);
  const outputPresetChoice = resolveTokenPresetChoice(slot.settingsPatch.outputTokens);

  return (
    <section className="tuning-lab-slot-display-panel tuning-lab-slot-module">
      <div className="tuning-lab-slot-module-head">
        <span className="status-label">Centralni display</span>
        <strong className="status-value">Context i Output</strong>
      </div>
      <p className="helper-text">
        Glavni signal za ovaj slot: koliko context-a drzis otvoreno i koliki output limit stvarno
        pustas u radu.
      </p>

      <div className="tuning-lab-slot-display-stack">
        <label className="tuning-lab-slot-display-box">
          <span>CTX</span>
          <strong className="tuning-lab-slot-display-readout">
            {formatDeckValue(slot.settingsPatch.context)}
          </strong>
          <span className="tuning-lab-slot-display-caption">Radni context</span>
          <div className="tuning-lab-slot-display-controls">
            <label className="tuning-lab-slot-display-control">
              <span className="tuning-lab-slot-display-control-label">Preset skala</span>
              <CustomSelect
                value={contextPresetChoice}
                options={TUNING_LAB_TOKEN_PRESET_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
                onChange={(value) => onPatchSlot(slot.id, { context: Number(value) })}
                placeholder="Slobodan broj"
                ariaLabel="Izaberi context preset"
              />
            </label>
            <label className="tuning-lab-slot-display-control">
              <span className="tuning-lab-slot-display-control-label">Ručni unos</span>
              <input
                className="tuning-lab-slot-display-input"
                type="number"
                value={slot.settingsPatch.context}
                aria-label="Unesi slobodan context broj"
                onChange={(event) =>
                  onPatchSlot(slot.id, { context: Number(event.target.value || 0) })
                }
              />
            </label>
          </div>
        </label>

        <label className="tuning-lab-slot-display-box">
          <span>OUT</span>
          <strong className="tuning-lab-slot-display-readout">
            {formatDeckValue(slot.settingsPatch.outputTokens)}
          </strong>
          <span className="tuning-lab-slot-display-caption">Limit izlaza</span>
          <div className="tuning-lab-slot-display-controls">
            <label className="tuning-lab-slot-display-control">
              <span className="tuning-lab-slot-display-control-label">Preset skala</span>
              <CustomSelect
                value={outputPresetChoice}
                options={TUNING_LAB_TOKEN_PRESET_OPTIONS.map((option) => ({
                  value: option.value,
                  label: option.label,
                }))}
                onChange={(value) => onPatchSlot(slot.id, { outputTokens: Number(value) })}
                placeholder="Slobodan broj"
                ariaLabel="Izaberi output preset"
              />
            </label>
            <label className="tuning-lab-slot-display-control">
              <span className="tuning-lab-slot-display-control-label">Ručni unos</span>
              <input
                className="tuning-lab-slot-display-input"
                type="number"
                value={slot.settingsPatch.outputTokens}
                aria-label="Unesi slobodan output broj"
                onChange={(event) =>
                  onPatchSlot(slot.id, { outputTokens: Number(event.target.value || 0) })
                }
              />
            </label>
          </div>
        </label>
      </div>
    </section>
  );
}
