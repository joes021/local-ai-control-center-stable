import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";

type TuningLabSlotDisplayPanelProps = {
  slot: TuningLabSlot;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

export function TuningLabSlotDisplayPanel({
  slot,
  onPatchSlot,
}: TuningLabSlotDisplayPanelProps) {
  return (
    <div className="tuning-lab-slot-display-panel">
      <label className="tuning-lab-slot-display-box">
        <span>Context</span>
        <input
          type="number"
          value={slot.settingsPatch.context}
          onChange={(event) => onPatchSlot(slot.id, { context: Number(event.target.value || 0) })}
        />
      </label>

      <label className="tuning-lab-slot-display-box">
        <span>Output</span>
        <input
          type="number"
          value={slot.settingsPatch.outputTokens}
          onChange={(event) =>
            onPatchSlot(slot.id, { outputTokens: Number(event.target.value || 0) })
          }
        />
      </label>
    </div>
  );
}
