import type { CompatibilityCheckRequest } from "../lib/types";
import type { ReactNode } from "react";
import { CompatibilityCalculatorPanel } from "./CompatibilityCalculatorPanel";

type Props = {
  isOpen: boolean;
  title: string;
  request: CompatibilityCheckRequest | null;
  onClose: () => void;
  headerActions?: ReactNode;
};

export function CompatibilityCalculatorModal({
  isOpen,
  title,
  request,
  onClose,
  headerActions,
}: Props) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="compat-modal-overlay" onClick={onClose}>
      <div className="compat-modal-shell" onClick={(event) => event.stopPropagation()}>
        <CompatibilityCalculatorPanel
          className="compat-surface compat-modal"
          title={title}
          request={request}
          onClose={onClose}
          headerActions={headerActions}
        />
      </div>
    </div>
  );
}
