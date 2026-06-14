import { PageFlowCard } from "../components/PageFlowCard";
import {
  SecondaryActionRail,
  type SecondaryActionRailItem,
} from "../components/shell/SecondaryActionRail";

type AdvancedPageProps = {
  onOpenBenchmark?: () => void;
  onOpenBrowser?: () => void;
  onOpenTuningLab?: () => void;
  onOpenCompatibility?: () => void;
  onOpenObservability?: () => void;
  onOpenKnowledge?: () => void;
  onOpenSearch?: () => void;
  onOpenWorkflows?: () => void;
  onOpenProjectMemory?: () => void;
  onOpenSettings?: () => void;
  onOpenLogs?: () => void;
  onOpenHelp?: () => void;
  onOpenRepair?: () => void;
  onOpenUpdates?: () => void;
  onOpenFleet?: () => void;
  onOpenJobs?: () => void;
};

type AdvancedGroup = {
  tone: "analysis" | "knowledge" | "focus" | "service";
  eyebrow: string;
  title: string;
  summary: string;
  whenToUse: string;
  result: string;
  routes: readonly string[];
};

const groups: readonly AdvancedGroup[] = [
  {
    tone: "analysis",
    eyebrow: "Analiza",
    title: "Brojke pre promene",
    summary:
      "Benchmark, Tuning Lab, kompatibilnost i telemetrija ostaju zajedno kada želiš da meriš throughput, fit i winner pre sledeće odluke.",
    whenToUse:
      "Ulaziš ovde kada menjaš model, profil ili batch i treba ti potvrda na živom runtime-u.",
    result:
      "Dobijaš jasan signal šta ostaje aktivno, šta je granično i gde je sledeći tuning korak.",
    routes: ["Benchmark", "Tuning Lab", "Kompatibilnost", "Telemetrija"],
  },
  {
    tone: "knowledge",
    eyebrow: "Znanje",
    title: "Izvor pre taska",
    summary:
      "Browser katalog, znanje, pretraga i radni tokovi služe da usidriš pravi dokument, veb trag ili lokalni kontekst pre nego što agent krene da radi.",
    whenToUse:
      "Ulaziš kada korisnik zna cilj, ali još nema pravi izvor ili dokaz na koji će se rad osloniti.",
    result:
      "Dobijaš čist ulaz, manje lutanja i konkretniji odgovor ili sledeći workflow.",
    routes: ["Browser", "Znanje", "Pretraga", "Radni tokovi"],
  },
  {
    tone: "focus",
    eyebrow: "Fokus",
    title: "Cilj, profil i trag",
    summary:
      "Project Memory, podešavanja, logovi i pomoć drže fokus projekta, aktivni profil i poslednji trag problema u jednom prolazu.",
    whenToUse:
      "Ulaziš kada rad traje duže, kada menjaš context ili kada želiš da potvrdiš šta je poslednja akcija uradila.",
    result:
      "Dobijaš manje gubitka konteksta i brži prelaz sa odluke na proverljiv rezultat.",
    routes: ["Project Memory", "Podešavanja", "Logovi", "Pomoć"],
  },
  {
    tone: "service",
    eyebrow: "Servis",
    title: "Oporavak i nadzor",
    summary:
      "Popravka, ažuriranja, flota i poslovi ostaju izdvojeni da glavni tok ne bude zatrpan, ali da servis ostane na jedan klik.",
    whenToUse:
      "Ulaziš kada sistem traži održavanje, proveru verzije ili pregled dužih pozadinskih tokova.",
    result:
      "Dobijaš kontrolisan servisni prolaz bez praznih kartica i bez skrivanja retkih, ali važnih alata.",
    routes: ["Popravka", "Ažuriranja", "Flota", "Poslovi"],
  },
];

export function AdvancedPage(props: AdvancedPageProps) {
  const railItems: SecondaryActionRailItem[] = [
    {
      code: "BNCH",
      title: "Otvori Benchmark",
      subtitle: "BRZINA + ISTORIJA",
      icon: "benchmark",
      tone: "primary",
      onClick: props.onOpenBenchmark,
    },
    {
      code: "LAB",
      title: "Otvori Tuning Lab",
      subtitle: "SLOTOVI + WINNER",
      icon: "tuning",
      onClick: props.onOpenTuningLab,
    },
    {
      code: "FIT",
      title: "Otvori kompatibilnost",
      subtitle: "VRAM FIT + KALKULATOR",
      icon: "compatibility",
      onClick: props.onOpenCompatibility,
    },
    {
      code: "LIVE",
      title: "Otvori telemetriju",
      subtitle: "ŽIVI SIGNAL + GPU",
      icon: "observability",
      onClick: props.onOpenObservability,
    },
    {
      code: "CAT",
      title: "Otvori Browser katalog",
      subtitle: "MODELI + IZVORI",
      icon: "browser",
      onClick: props.onOpenBrowser,
    },
    {
      code: "KNOW",
      title: "Otvori Znanje",
      subtitle: "DOKUMENTI + KONTEKST",
      icon: "knowledge",
      onClick: props.onOpenKnowledge,
    },
    {
      code: "SRC",
      title: "Otvori Pretragu",
      subtitle: "WEB + LOKALNI TRAG",
      icon: "search",
      onClick: props.onOpenSearch,
    },
    {
      code: "FLOW",
      title: "Otvori Radne tokove",
      subtitle: "PRESET + TOK",
      icon: "workflows",
      onClick: props.onOpenWorkflows,
    },
    {
      code: "MEM",
      title: "Otvori Project Memory",
      subtitle: "CILJ + PRAVILA",
      icon: "memory",
      onClick: props.onOpenProjectMemory,
    },
    {
      code: "CFG",
      title: "Otvori Podešavanja",
      subtitle: "PROFIL + CONTEXT",
      icon: "settings",
      onClick: props.onOpenSettings,
    },
    {
      code: "LOG",
      title: "Otvori Logove",
      subtitle: "TRAG + PORUKE",
      icon: "logs",
      onClick: props.onOpenLogs,
    },
    {
      code: "HELP",
      title: "Otvori Pomoć",
      subtitle: "VODIČ + POMOĆ",
      icon: "help",
      onClick: props.onOpenHelp,
    },
    {
      code: "REP",
      title: "Otvori Popravku",
      subtitle: "OPORAVAK + SERVIS",
      icon: "repair",
      onClick: props.onOpenRepair,
    },
    {
      code: "UPD",
      title: "Otvori Ažuriranja",
      subtitle: "VERZIJA + STATUS",
      icon: "updates",
      onClick: props.onOpenUpdates,
    },
    {
      code: "FLT",
      title: "Otvori Flotu",
      subtitle: "MREŽA + PREGLED",
      icon: "fleet",
      onClick: props.onOpenFleet,
    },
    {
      code: "JOB",
      title: "Otvori Poslove",
      subtitle: "RED + PRAĆENJE",
      icon: "jobs",
      onClick: props.onOpenJobs,
    },
  ];

  return (
    <div className="runtimepilot-secondary-hub">
      <div className="runtimepilot-secondary-hub-main">
        <PageFlowCard
          title="Sekundarni hub"
          summary="Napredno više nije drugi komandni centar. Levo ostaju samo stvarne oblasti rada, a desno su direktni klikovi ka konkretnim ekranima i rezultatima."
          steps={[
            {
              title: "Nađi pravu oblast",
              detail: "Prvo proveri da li ti treba analiza, izvor, fokus projekta ili servisni prolaz.",
            },
            {
              title: "Otvori konkretan ekran",
              detail: "Svaki klik sa rail-a vodi pravo na alat ili rezultat bez placeholder modula i mrtvih footer kartica.",
            },
            {
              title: "Vrati se po sledeći korak",
              detail: "Kad završiš jednu proveru, Napredno ostaje čista mapa sekundarnih akcija.",
            },
          ]}
        />

        <section className="status-card runtimepilot-faceplate-module runtimepilot-section-shell runtimepilot-secondary-hub-panel">
          <div className="runtimepilot-advanced-summary-head">
            <div>
              <span className="status-label">Grupisani izlazi</span>
              <strong className="status-value">Četiri stvarne zone umesto placeholder modula</strong>
            </div>
            <p className="helper-text runtimepilot-advanced-summary-copy">
              Sadržaj levo objašnjava kada ulaziš u određenu zonu i kakav rezultat dobijaš, bez lažnih readout
              kartica koje izgledaju klikabilno, a ništa ne rade.
            </p>
          </div>

          <div className="runtimepilot-advanced-summary-grid">
            {groups.map((group) => (
              <article
                className={`runtimepilot-advanced-summary-card runtimepilot-advanced-summary-card-${group.tone}`}
                key={group.title}
              >
                <span className="status-label">{group.eyebrow}</span>
                <strong className="runtimepilot-advanced-summary-title">{group.title}</strong>
                <p className="helper-text runtimepilot-advanced-summary-text">{group.summary}</p>
                <div className="runtimepilot-advanced-summary-block">
                  <span className="status-label">Kada ulaziš</span>
                  <p className="helper-text">{group.whenToUse}</p>
                </div>
                <div className="runtimepilot-advanced-summary-block">
                  <span className="status-label">Šta dobijaš</span>
                  <p className="helper-text">{group.result}</p>
                </div>
                <div className="runtimepilot-advanced-summary-routes">
                  {group.routes.map((route) => (
                    <span className="browser-chip" key={route}>
                      {route}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>

      <SecondaryActionRail
        eyebrow="Action rail"
        title="Stvarne akcije"
        summary="Otvori samo konkretan alat ili rezultat. Sekundarne strane više ne dupliraju komande kroz više slojeva."
        items={railItems}
      />
    </div>
  );
}
