export type HomeHiFiSignalItem = {
  label: string;
  value: string;
  detail: string;
  tone?: "success" | "accent" | "signal";
};

export function HomeHiFiSignalRail({ items }: { items: readonly HomeHiFiSignalItem[] }) {
  return (
    <div className="runtimepilot-home-hifi-rail">
      {items.map((item) => (
        <article
          key={`${item.label}-${item.value}`}
          className={`runtimepilot-home-hifi-rail-item runtimepilot-home-hifi-rail-item-${item.tone ?? "accent"}`}
        >
          <span className="status-label">{item.label}</span>
          <strong className="status-value">{item.value}</strong>
          <p className="helper-text">{item.detail}</p>
        </article>
      ))}
    </div>
  );
}
