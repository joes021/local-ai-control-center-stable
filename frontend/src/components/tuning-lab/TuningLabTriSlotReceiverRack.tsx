import type { TuningLabSettingsPatch, TuningLabSlot } from "../../lib/types";

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
            <span className="status-label">{slot.label}</span>
            <strong className="status-value">{slot.source}</strong>
            <p className="helper-text">{buildInferenceSummary(slot)}</p>
            <div className="tuning-lab-compact-grid">
              <label className="settings-compact-field">
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
              <label className="settings-compact-field">
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
              <label className="settings-compact-field">
                <span>Context</span>
                <input
                  type="number"
                  value={slot.settingsPatch.context}
                  onChange={(event) =>
                    onPatchSlot(slot.id, { context: Number(event.target.value || 0) })
                  }
                />
              </label>
              <label className="settings-compact-field">
                <span>Output</span>
                <input
                  type="number"
                  value={slot.settingsPatch.outputTokens}
                  onChange={(event) =>
                    onPatchSlot(slot.id, { outputTokens: Number(event.target.value || 0) })
                  }
                />
              </label>
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
