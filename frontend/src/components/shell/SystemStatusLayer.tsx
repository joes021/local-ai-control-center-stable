import { useEffect, useRef, useState, type ReactNode } from "react";

import { LiveResourceStrip, useLiveResourceStripState } from "../LiveResourceStrip";

type SystemStatusLayerProps = {
  activeModelStrip: ReactNode;
  onOpenSettingsSection?: (sectionId: string) => void;
};

const STICKY_VISIBILITY_OFFSET = 24;

export function SystemStatusLayer({
  activeModelStrip,
  onOpenSettingsSection,
}: SystemStatusLayerProps) {
  const fullLayerRef = useRef<HTMLDivElement | null>(null);
  const liveResourceStripState = useLiveResourceStripState();
  const [stickyVisible, setStickyVisible] = useState(false);

  useEffect(() => {
    const syncStickyVisibility = () => {
      const fullLayer = fullLayerRef.current;
      if (!fullLayer) {
        setStickyVisible(false);
        return;
      }

      setStickyVisible(fullLayer.getBoundingClientRect().bottom <= STICKY_VISIBILITY_OFFSET);
    };

    syncStickyVisibility();
    window.addEventListener("scroll", syncStickyVisibility, { passive: true });
    window.addEventListener("resize", syncStickyVisibility);

    return () => {
      window.removeEventListener("scroll", syncStickyVisibility);
      window.removeEventListener("resize", syncStickyVisibility);
    };
  }, []);

  return (
    <div className="runtimepilot-system-status-layer">
      <div className="runtimepilot-system-status-layer-full" ref={fullLayerRef}>
        <div className="runtimepilot-status-rack">{activeModelStrip}</div>
        <LiveResourceStrip
          onOpenSettingsSection={onOpenSettingsSection}
          state={liveResourceStripState}
        />
      </div>
      <div
        aria-hidden={stickyVisible ? undefined : true}
        className="runtimepilot-system-status-layer-sticky"
        data-visible={stickyVisible ? "true" : "false"}
      >
        {stickyVisible ? (
          <div className="runtimepilot-system-status-layer-compact">
            <div className="runtimepilot-status-rack runtimepilot-status-rack-compact">
              {activeModelStrip}
            </div>
            <LiveResourceStrip
              compact
              onOpenSettingsSection={onOpenSettingsSection}
              state={liveResourceStripState}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
