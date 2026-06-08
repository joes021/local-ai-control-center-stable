import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";
import { TuningLabSlotDisplayPanel } from "./TuningLabSlotDisplayPanel";
import { TuningLabSlotIdentityPanel } from "./TuningLabSlotIdentityPanel";

type TuningLabTriSlotReceiverRackProps = {
  slots: TuningLabSlot[];
  buildInferenceSummary: (slot: TuningLabSlot) => string;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

const PRECISION_FIELDS = [
  ["Temperature", "temperature"],
  ["Top-k", "topK"],
  ["Top-p", "topP"],
  ["Min-p", "minP"],
  ["Repeat", "repeatPenalty"],
  ["Last N", "repeatLastN"],
  ["Presence", "presencePenalty"],
  ["Frequency", "frequencyPenalty"],
  ["Seed", "seed"],
] as const;

function getFieldStep(key: keyof TuningLabSettingsPatch) {
  return key === "repeatLastN" || key === "seed" || key === "topK" ? 1 : 0.05;
}

export function TuningLabTriSlotReceiverRack({
  slots,
  buildInferenceSummary,
  onPatchSlot,
}: TuningLabTriSlotReceiverRackProps) {
  return (
    <div className="tuning-lab-receiver-rack">
      <div className="tuning-lab-slot-grid">
        {slots.map((slot) => (
          <article className="status-card tuning-lab-slot-card tuning-lab-slot-row" key={slot.id}>
            <TuningLabSlotIdentityPanel
              helperText={buildInferenceSummary(slot)}
              slot={slot}
              onPatchSlot={onPatchSlot}
            />

            <TuningLabSlotDisplayPanel slot={slot} onPatchSlot={onPatchSlot} />

            <div className="tuning-lab-compact-grid">
              {PRECISION_FIELDS.map(([label, key]) => (
                <label className="settings-compact-field" key={`${slot.id}-${key}`}>
                  <span>{label}</span>
                  <input
                    type="number"
                    step={getFieldStep(key)}
                    value={slot.settingsPatch[key]}
                    onChange={(event) =>
                      onPatchSlot(slot.id, {
                        [key]: Number(event.target.value || 0),
                      } as Partial<TuningLabSettingsPatch>)
                    }
                  />
                </label>
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
