import type { CSSProperties } from "react";

import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";
import {
  TUNING_LAB_SLOT_CONTROL_GROUPS,
  type TuningLabPrecisionField,
} from "./tuningLabSlotControlGroups";

type TuningLabSlotPrecisionRackProps = {
  slot: TuningLabSlot;
  onPatchSlot: (slotId: string, patch: Partial<TuningLabSettingsPatch>) => void;
};

function normalizeValue(field: TuningLabPrecisionField, value: number) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  const span = field.max - field.min;
  if (span <= 0) {
    return 0;
  }
  const ratio = ((value - field.min) / span) * 100;
  return Math.max(0, Math.min(100, ratio));
}

export function TuningLabSlotPrecisionRack({
  slot,
  onPatchSlot,
}: TuningLabSlotPrecisionRackProps) {
  return (
    <section className="tuning-lab-slot-precision-rack tuning-lab-slot-module">
      <div className="tuning-lab-slot-module-head">
        <span className="status-label">Mixer rack</span>
        <strong className="status-value">Svih 9 finih kontrola</strong>
      </div>
      <p className="helper-text">
        Sampling, stabilnost i bias stoje zajedno da odmah vidis ceo miks, bez lutanja po slotu.
      </p>

      <div className="tuning-lab-slot-mixer-rack">
        {TUNING_LAB_SLOT_CONTROL_GROUPS.map((group) => (
          <section className="tuning-lab-slot-precision-group" key={`${slot.id}-${group.title}`}>
            <span className="status-label">{group.title}</span>
            <div className="tuning-lab-slot-precision-grid">
              {group.fields.map((field) => {
                const value = Number(slot.settingsPatch[field.key]);
                return (
                  <label
                    className="tuning-lab-slot-precision-control"
                    key={`${slot.id}-${field.key}`}
                    style={
                      {
                        "--tuning-lab-slider-fill": `${normalizeValue(field, value)}%`,
                      } as CSSProperties
                    }
                  >
                    <span className="tuning-lab-slot-precision-head">
                      <span>{field.label}</span>
                      <strong>{value}</strong>
                    </span>
                    <input
                      className="tuning-lab-slot-precision-slider"
                      type="range"
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      value={value}
                      onChange={(event) =>
                        onPatchSlot(slot.id, {
                          [field.key]: Number(event.target.value || 0),
                        } as Partial<TuningLabSettingsPatch>)
                      }
                    />
                    <input
                      className="tuning-lab-slot-precision-input"
                      type="number"
                      min={field.min}
                      max={field.max}
                      step={field.step}
                      value={value}
                      onChange={(event) =>
                        onPatchSlot(slot.id, {
                          [field.key]: Number(event.target.value || 0),
                        } as Partial<TuningLabSettingsPatch>)
                      }
                    />
                  </label>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
