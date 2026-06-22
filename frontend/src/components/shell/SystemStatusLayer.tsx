import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

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
  const compactLayerRef = useRef<HTMLDivElement | null>(null);
  const liveResourceStripState = useLiveResourceStripState();
  const [stickyVisible, setStickyVisible] = useState(false);
  const [stickyReserveHeight, setStickyReserveHeight] = useState(0);

  useEffect(() => {
    const fullLayer = fullLayerRef.current;
    const syncStickyVisibility = () => {
      if (!fullLayer) {
        setStickyVisible(false);
        return;
      }

      setStickyVisible(fullLayer.getBoundingClientRect().bottom <= STICKY_VISIBILITY_OFFSET);
    };

    syncStickyVisibility();
    const resizeObserver =
      fullLayer && typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            syncStickyVisibility();
          })
        : null;
    if (resizeObserver && fullLayer) {
      resizeObserver.observe(fullLayer);
    }
    window.addEventListener("scroll", syncStickyVisibility, { passive: true });
    window.addEventListener("resize", syncStickyVisibility);

    return () => {
      window.removeEventListener("scroll", syncStickyVisibility);
      window.removeEventListener("resize", syncStickyVisibility);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, []);

  useEffect(() => {
    const compactLayer = compactLayerRef.current;
    const syncStickyReserveHeight = () => {
      setStickyReserveHeight(compactLayer ? Math.ceil(compactLayer.getBoundingClientRect().height) : 0);
    };

    syncStickyReserveHeight();
    const resizeObserver =
      compactLayer && typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
            syncStickyReserveHeight();
          })
        : null;
    if (resizeObserver && compactLayer) {
      resizeObserver.observe(compactLayer);
    }
    window.addEventListener("resize", syncStickyReserveHeight);

    return () => {
      window.removeEventListener("resize", syncStickyReserveHeight);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, []);

  const stickyStyle = {
    "--runtimepilot-system-status-sticky-reserve": stickyVisible ? `${stickyReserveHeight}px` : "0px",
  } as CSSProperties;

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
        style={stickyStyle}
      >
        <div className="runtimepilot-system-status-layer-compact" ref={compactLayerRef}>
          <div className="runtimepilot-status-rack runtimepilot-status-rack-compact">
            {activeModelStrip}
          </div>
          <LiveResourceStrip
            compact
            onOpenSettingsSection={onOpenSettingsSection}
            state={liveResourceStripState}
          />
        </div>
      </div>
    </div>
  );
}
