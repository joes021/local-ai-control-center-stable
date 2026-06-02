import runtimePilotWordmark from "../assets/runtimepilot-wordmark.png";

export function BrandLockup() {
  return (
    <div className="brand-lockup" aria-hidden="true">
      <img
        alt=""
        className="brand-lockup-wordmark"
        draggable="false"
        src={runtimePilotWordmark}
      />
    </div>
  );
}
