import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";
import { TuningLabSlotDisplayPanel } from "./TuningLabSlotDisplayPanel";
import { TuningLabSlotIdentityPanel } from "./TuningLabSlotIdentityPanel";
import { TuningLabSlotPrecisionRack } from "./TuningLabSlotPrecisionRack";

type TuningLabTriSlotReceiverRackProps = {
  slots: TuningLabSlot[];
  referenceSlots: TuningLabSlot[];
  buildInferenceSummary: (slot: TuningLabSlot) => string;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

function hasDraftChanges(referenceSlot: TuningLabSlot | undefined, slot: TuningLabSlot) {
  if (!referenceSlot) {
    return false;
  }
  const keys = Object.keys(referenceSlot.settingsPatch) as Array<keyof TuningLabSettingsPatch>;
  return keys.some((key) => referenceSlot.settingsPatch[key] !== slot.settingsPatch[key]);
}

export function TuningLabTriSlotReceiverRack({
  slots,
  referenceSlots,
  buildInferenceSummary,
  onPatchSlot,
}: TuningLabTriSlotReceiverRackProps) {
  return (
    <div className="tuning-lab-receiver-rack">
      <div className="tuning-lab-slot-grid">
        {slots.map((slot) => {
          const referenceSlot = referenceSlots.find((candidate) => candidate.id === slot.id);
          const isDraftChanged = hasDraftChanges(referenceSlot, slot);
          const isRecommended = slot.id === "recommended";
          const isActive = slot.status === "running" || slot.status === "completed" || Boolean(slot.taskCompleted);
          const slotClassName = [
            "status-card",
            "tuning-lab-slot-card",
            "tuning-lab-slot-row",
            isDraftChanged ? "tuning-lab-slot-state-draft" : "",
            isRecommended ? "tuning-lab-slot-state-recommended" : "",
            isActive ? "tuning-lab-slot-state-active" : "",
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <article className={slotClassName} key={slot.id}>
              <div className="tuning-lab-slot-zones">
                <TuningLabSlotIdentityPanel
                  helperText={buildInferenceSummary(slot)}
                  isActive={isActive}
                  isDraftChanged={isDraftChanged}
                  isRecommended={isRecommended}
                  slot={slot}
                  onPatchSlot={onPatchSlot}
                />

                <TuningLabSlotDisplayPanel slot={slot} onPatchSlot={onPatchSlot} />

                <TuningLabSlotPrecisionRack slot={slot} onPatchSlot={onPatchSlot} />
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
