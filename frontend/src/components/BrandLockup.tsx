import runtimePilotWordmark from "../assets/runtimepilot-wordmark.png";

type BrandLockupProps = {
  version?: string | null;
};

export function BrandLockup({ version }: BrandLockupProps) {
  const versionLabel = version ? `v${version}` : null;

  return (
    <div className="brand-lockup" aria-hidden="true">
      <img
        alt=""
        className="brand-lockup-wordmark"
        draggable="false"
        src={runtimePilotWordmark}
      />
      {versionLabel ? <span className="brand-lockup-version">{versionLabel}</span> : null}
    </div>
  );
}
