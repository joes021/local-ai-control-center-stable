import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";
import { TuningLabSlotDisplayPanel } from "./TuningLabSlotDisplayPanel";
import { TuningLabSlotIdentityPanel } from "./TuningLabSlotIdentityPanel";
import { TuningLabSlotPrecisionRack } from "./TuningLabSlotPrecisionRack";

type TuningLabTriSlotReceiverRackProps = {
  slots: TuningLabSlot[];
  buildInferenceSummary: (slot: TuningLabSlot) => string;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

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

            <TuningLabSlotPrecisionRack slot={slot} onPatchSlot={onPatchSlot} />
          </article>
        ))}
      </div>
    </div>
  );
}
