import type { TuningLabSettingsPatch } from "../../lib/types";

export type TuningLabPrecisionField = {
  key: keyof TuningLabSettingsPatch;
  label: string;
  max: number;
  min: number;
  step: number;
};

export type TuningLabPrecisionGroup = {
  title: string;
  fields: TuningLabPrecisionField[];
};

export const TUNING_LAB_SLOT_CONTROL_GROUPS: TuningLabPrecisionGroup[] = [
  {
    title: "Sampling",
    fields: [
      { key: "temperature", label: "Temperature", min: 0, max: 1.5, step: 0.05 },
      { key: "topK", label: "Top-k", min: 0, max: 100, step: 1 },
      { key: "topP", label: "Top-p", min: 0, max: 1, step: 0.05 },
    ],
  },
  {
    title: "Stability",
    fields: [
      { key: "minP", label: "Min-p", min: 0, max: 1, step: 0.05 },
      { key: "repeatPenalty", label: "Repeat", min: 0.8, max: 1.4, step: 0.05 },
      { key: "repeatLastN", label: "Last N", min: 0, max: 256, step: 1 },
    ],
  },
  {
    title: "Bias",
    fields: [
      { key: "presencePenalty", label: "Presence", min: 0, max: 2, step: 0.05 },
      { key: "frequencyPenalty", label: "Frequency", min: 0, max: 2, step: 0.05 },
      { key: "seed", label: "Seed", min: -1, max: 100, step: 1 },
    ],
  },
];
