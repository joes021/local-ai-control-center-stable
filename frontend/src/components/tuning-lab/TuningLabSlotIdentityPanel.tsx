import { CustomSelect } from "../CustomSelect";
import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";

type TuningLabSlotIdentityPanelProps = {
  helperText: string;
  isActive: boolean;
  isDraftChanged: boolean;
  isRecommended: boolean;
  slot: TuningLabSlot;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

const PROFILE_OPTIONS = [
  { value: "balanced", label: "balanced" },
  { value: "speed", label: "speed" },
  { value: "video", label: "video" },
] as const;

const THINKING_OPTIONS = [
  { value: "no-thinking", label: "no-thinking" },
  { value: "low", label: "low" },
  { value: "mid", label: "mid" },
  { value: "high", label: "high" },
  { value: "extra-high", label: "extra-high" },
] as const;

export function TuningLabSlotIdentityPanel({
  helperText,
  isActive,
  isDraftChanged,
  isRecommended,
  slot,
  onPatchSlot,
}: TuningLabSlotIdentityPanelProps) {
  return (
    <section className="tuning-lab-slot-identity-panel tuning-lab-slot-module">
      <div className="tuning-lab-slot-module-head">
        <span className="status-label">Signal chain</span>
        <strong className="status-value">Profil, thinking i source</strong>
      </div>
      <p className="helper-text">{helperText}</p>

      <div className="tuning-lab-slot-square-control-grid">
        <label className="tuning-lab-slot-square-control tuning-lab-slot-square-select">
          <span>Profil</span>
          <CustomSelect
            value={slot.settingsPatch.profile}
            options={PROFILE_OPTIONS.map((option) => ({ ...option }))}
            onChange={(value) => onPatchSlot(slot.id, { profile: value })}
            ariaLabel={`Izaberi profil za ${slot.label}`}
          />
        </label>

        <label className="tuning-lab-slot-square-control tuning-lab-slot-square-select">
          <span>Thinking</span>
          <CustomSelect
            value={slot.settingsPatch.thinkingMode}
            options={THINKING_OPTIONS.map((option) => ({ ...option }))}
            onChange={(value) => onPatchSlot(slot.id, { thinkingMode: value })}
            ariaLabel={`Izaberi thinking režim za ${slot.label}`}
          />
        </label>

        <div className="tuning-lab-slot-square-control tuning-lab-slot-square-control-wide tuning-lab-slot-square-source">
          <span>Source</span>
          <strong>{slot.source}</strong>
        </div>
      </div>

      <div className="tuning-lab-slot-led-row">
        {isDraftChanged ? (
          <span className="tuning-lab-slot-state-chip tuning-lab-slot-state-draft">izmenjeno</span>
        ) : null}
        {isRecommended ? (
          <span className="tuning-lab-slot-state-chip tuning-lab-slot-state-recommended">
            preporučeno
          </span>
        ) : null}
        {isActive ? (
          <span className="tuning-lab-slot-state-chip tuning-lab-slot-state-active">aktivno</span>
        ) : null}
        <span>{slot.status || "draft"}</span>
        <span>{slot.source}</span>
      </div>
    </section>
  );
}
