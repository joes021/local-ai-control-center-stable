type RuntimePilotIconName =
  | "home"
  | "server"
  | "models"
  | "opencode"
  | "search"
  | "settings"
  | "browser"
  | "knowledge"
  | "compatibility"
  | "observability"
  | "benchmark"
  | "tuning"
  | "workflows"
  | "jobs"
  | "fleet"
  | "logs"
  | "repair"
  | "updates"
  | "help"
  | "runtime"
  | "control"
  | "privacy"
  | "telemetry"
  | "memory"
  | "cpu"
  | "play"
  | "stop"
  | "reload";

export type { RuntimePilotIconName };

function iconPaths(name: RuntimePilotIconName) {
  switch (name) {
    case "home":
      return (
        <>
          <path d="M4.5 10.5 12 4l7.5 6.5" />
          <path d="M6.75 9.75V20h10.5V9.75" />
        </>
      );
    case "server":
      return (
        <>
          <rect x="4" y="4" width="16" height="6" rx="2" />
          <rect x="4" y="14" width="16" height="6" rx="2" />
          <path d="M8 7h.01M8 17h.01M12 7h4M12 17h4" />
        </>
      );
    case "models":
      return (
        <>
          <rect x="7" y="7" width="10" height="10" rx="2" />
          <path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
        </>
      );
    case "opencode":
      return (
        <>
          <path d="m8 9-3 3 3 3" />
          <path d="m16 9 3 3-3 3" />
          <path d="m13.5 5-3 14" />
        </>
      );
    case "search":
      return (
        <>
          <circle cx="11" cy="11" r="5.5" />
          <path d="m15.5 15.5 4 4" />
        </>
      );
    case "settings":
      return (
        <>
          <path d="M4 7h8M15 7h5M4 17h5M12 17h8M12 4v6M9 14v6" />
        </>
      );
    case "browser":
      return (
        <>
          <rect x="3.5" y="5" width="17" height="14" rx="2.5" />
          <path d="M3.5 8.5h17M7 12h3M12 12h5M7 16h8" />
        </>
      );
    case "knowledge":
      return (
        <>
          <path d="M6 5.5h7.5A2.5 2.5 0 0 1 16 8v10H8.2A2.2 2.2 0 0 0 6 20.2Z" />
          <path d="M18 5.5h-4.5A2.5 2.5 0 0 0 11 8v10h6.8A2.2 2.2 0 0 1 20 20.2V7.5A2 2 0 0 0 18 5.5Z" />
        </>
      );
    case "compatibility":
      return (
        <>
          <path d="M8.5 12a3.5 3.5 0 0 1 3.5-3.5h3" />
          <path d="M15.5 12A3.5 3.5 0 0 1 12 15.5H9" />
          <path d="M8 9.5 5.5 12 8 14.5M16 9.5 18.5 12 16 14.5" />
        </>
      );
    case "observability":
    case "telemetry":
      return (
        <>
          <path d="M4 17h16" />
          <path d="M6 17a6 6 0 0 1 12 0" />
          <path d="M9 17a3 3 0 0 1 6 0" />
          <circle cx="12" cy="11" r="1.25" fill="currentColor" stroke="none" />
        </>
      );
    case "benchmark":
      return (
        <>
          <path d="M5 18V9M10 18V6M15 18v-4M20 18V8" />
          <path d="M4 18h17" />
        </>
      );
    case "tuning":
      return (
        <>
          <circle cx="12" cy="12" r="6" />
          <circle cx="12" cy="12" r="2" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        </>
      );
    case "workflows":
      return (
        <>
          <circle cx="6" cy="7" r="2" />
          <circle cx="18" cy="12" r="2" />
          <circle cx="8" cy="18" r="2" />
          <path d="M7.5 8.5 16.5 11M16.5 13 9.5 17" />
        </>
      );
    case "jobs":
      return (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 7v5l3 2" />
        </>
      );
    case "fleet":
      return (
        <>
          <circle cx="6.5" cy="12" r="2.25" />
          <circle cx="17.5" cy="6.5" r="2.25" />
          <circle cx="17.5" cy="17.5" r="2.25" />
          <path d="M8.5 11 15.5 7.5M8.5 13l7 3.5" />
        </>
      );
    case "logs":
      return (
        <>
          <path d="M7 6.5h10M7 11.5h10M7 16.5h7" />
          <rect x="4" y="4" width="16" height="16" rx="3" />
        </>
      );
    case "repair":
      return (
        <>
          <path d="m14 7 3-3 3 3-3 3" />
          <path d="M17 7a6 6 0 0 0-8.5 8.5" />
          <path d="m10 17-3 3-3-3 3-3" />
          <path d="M7 17A6 6 0 0 0 15.5 8.5" />
        </>
      );
    case "updates":
      return (
        <>
          <path d="M12 4v8" />
          <path d="m8.5 8.5 3.5 3.5 3.5-3.5" />
          <path d="M5 15v3h14v-3" />
        </>
      );
    case "help":
      return (
        <>
          <circle cx="12" cy="12" r="8" />
          <path d="M9.4 9.2a2.8 2.8 0 1 1 4.8 2c-.65.7-1.42 1.1-1.92 1.78-.28.37-.38.72-.38 1.22" />
          <circle cx="12" cy="17.2" r="0.9" fill="currentColor" stroke="none" />
        </>
      );
    case "runtime":
      return (
        <>
          <path d="M6 16a6 6 0 1 1 12 0" />
          <path d="M12 12 16.5 8.5" />
          <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
        </>
      );
    case "privacy":
      return (
        <>
          <path d="M12 4 6 6.5v5.75c0 3.35 2.3 6.45 6 7.75 3.7-1.3 6-4.4 6-7.75V6.5Z" />
          <path d="M10 12.5 11.5 14 15 10.5" />
        </>
      );
    case "memory":
      return (
        <>
          <rect x="6.5" y="7" width="11" height="10" rx="2" />
          <path d="M9 4v3M15 4v3M9 17v3M15 17v3M3.5 10h3M17.5 10h3M3.5 14h3M17.5 14h3" />
        </>
      );
    case "cpu":
      return (
        <>
          <rect x="7" y="7" width="10" height="10" rx="2" />
          <path d="M9 9h6v6H9zM9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" />
        </>
      );
    case "play":
      return (
        <>
          <path d="M8 6.5v11l8.5-5.5Z" fill="currentColor" stroke="none" />
        </>
      );
    case "stop":
      return (
        <>
          <rect x="7" y="7" width="10" height="10" rx="1.75" fill="currentColor" stroke="none" />
        </>
      );
    case "reload":
      return (
        <>
          <path d="M17 7.5V4.5h-3" />
          <path d="M17 4.5 13 8.5" />
          <path d="M17 12a5 5 0 1 1-1.25-3.3" />
        </>
      );
    case "control":
    default:
      return (
        <>
          <path d="M5 12h6" />
          <path d="M13 12h6" />
          <circle cx="12" cy="12" r="2.75" />
          <path d="M12 5V3M12 21v-2M5 12H3M21 12h-2" />
        </>
      );
  }
}

export function RuntimePilotIcon({
  name,
  className = "",
}: {
  name: RuntimePilotIconName;
  className?: string;
}) {
  const normalized = className.trim();

  return (
    <span
      aria-hidden="true"
      className={normalized ? `runtimepilot-icon ${normalized}` : "runtimepilot-icon"}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        {iconPaths(name)}
      </svg>
    </span>
  );
}
