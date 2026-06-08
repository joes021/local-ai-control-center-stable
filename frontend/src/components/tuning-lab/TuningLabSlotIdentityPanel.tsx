import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";

type TuningLabSlotIdentityPanelProps = {
  helperText: string;
  isActive: boolean;
  isDraftChanged: boolean;
  isRecommended: boolean;
  slot: TuningLabSlot;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

export function TuningLabSlotIdentityPanel({
  helperText,
  isActive,
  isDraftChanged,
  isRecommended,
  slot,
  onPatchSlot,
}: TuningLabSlotIdentityPanelProps) {
  return (
    <div className="tuning-lab-slot-identity-panel">
      <span className="status-label">{slot.label}</span>
      <strong className="status-value">{slot.summary || slot.label}</strong>
      <p className="helper-text">{helperText}</p>

      <div className="tuning-lab-slot-square-control-grid">
        <label className="tuning-lab-slot-square-control">
          <span>Profil</span>
          <select
            value={slot.settingsPatch.profile}
            onChange={(event) => onPatchSlot(slot.id, { profile: event.target.value })}
          >
            <option value="balanced">balanced</option>
            <option value="speed">speed</option>
            <option value="video">video</option>
          </select>
        </label>

        <label className="tuning-lab-slot-square-control">
          <span>Thinking</span>
          <select
            value={slot.settingsPatch.thinkingMode}
            onChange={(event) => onPatchSlot(slot.id, { thinkingMode: event.target.value })}
          >
            <option value="no-thinking">no-thinking</option>
            <option value="low">low</option>
            <option value="mid">mid</option>
            <option value="high">high</option>
            <option value="extra-high">extra-high</option>
          </select>
        </label>

        <div className="tuning-lab-slot-square-control">
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
    </div>
  );
}
