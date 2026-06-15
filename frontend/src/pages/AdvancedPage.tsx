import { SupportPageDeck } from "../components/shell/SupportPageDeck";

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
  routes: readonly {
    title: string;
    subtitle: string;
    onClick?: () => void;
  }[];
};

export function AdvancedPage(props: AdvancedPageProps) {
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
      routes: [
        {
          title: "Otvori Benchmark",
          subtitle: "BRZINA + ISTORIJA",
          onClick: props.onOpenBenchmark,
        },
        {
          title: "Otvori Tuning Lab",
          subtitle: "SLOTOVI + WINNER",
          onClick: props.onOpenTuningLab,
        },
        {
          title: "Otvori kompatibilnost",
          subtitle: "VRAM FIT + KALKULATOR",
          onClick: props.onOpenCompatibility,
        },
        {
          title: "Otvori telemetriju",
          subtitle: "ŽIVI SIGNAL + GPU",
          onClick: props.onOpenObservability,
        },
      ],
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
      routes: [
        {
          title: "Otvori Browser katalog",
          subtitle: "MODELI + IZVORI",
          onClick: props.onOpenBrowser,
        },
        {
          title: "Otvori Znanje",
          subtitle: "DOKUMENTI + KONTEKST",
          onClick: props.onOpenKnowledge,
        },
        {
          title: "Otvori Pretragu",
          subtitle: "WEB + LOKALNI TRAG",
          onClick: props.onOpenSearch,
        },
        {
          title: "Otvori Radne tokove",
          subtitle: "PRESET + TOK",
          onClick: props.onOpenWorkflows,
        },
      ],
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
      routes: [
        {
          title: "Otvori Project Memory",
          subtitle: "CILJ + PRAVILA",
          onClick: props.onOpenProjectMemory,
        },
        {
          title: "Otvori Podešavanja",
          subtitle: "PROFIL + CONTEXT",
          onClick: props.onOpenSettings,
        },
        {
          title: "Otvori Logove",
          subtitle: "TRAG + PORUKE",
          onClick: props.onOpenLogs,
        },
        {
          title: "Otvori Pomoć",
          subtitle: "VODIČ + POMOĆ",
          onClick: props.onOpenHelp,
        },
      ],
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
      routes: [
        {
          title: "Otvori Popravku",
          subtitle: "OPORAVAK + SERVIS",
          onClick: props.onOpenRepair,
        },
        {
          title: "Otvori Ažuriranja",
          subtitle: "VERZIJA + STATUS",
          onClick: props.onOpenUpdates,
        },
        {
          title: "Otvori Flotu",
          subtitle: "MREŽA + PREGLED",
          onClick: props.onOpenFleet,
        },
        {
          title: "Otvori Poslove",
          subtitle: "RED + PRAĆENJE",
          onClick: props.onOpenJobs,
        },
      ],
    },
  ];

  return (
    <div className="runtimepilot-secondary-hub runtimepilot-secondary-hub-fullwidth">
      <SupportPageDeck
        eyebrow="Sekundarni hub"
        title="Napredno bez dupliranih komandi"
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
        resultHint={
          <>
            <span className="status-label">Brzi raspored</span>
            <strong className="status-value">Četiri radne zone</strong>
            <p className="helper-text">
              Analiza, znanje, fokus i servis sada ostaju kao jasne celine. Desni rail više nije
              duplikat, već samo direktan skok u konkretan alat.
            </p>
          </>
        }
      />

      <section className="status-card runtimepilot-faceplate-module runtimepilot-section-shell runtimepilot-secondary-hub-panel">
        <div className="runtimepilot-advanced-summary-head">
          <div>
            <span className="status-label">Grupisani izlazi</span>
            <strong className="status-value">Četiri stvarne zone umesto placeholder modula</strong>
          </div>
          <p className="helper-text runtimepilot-advanced-summary-copy">
            Sadržaj levo objašnjava kada ulaziš u određenu zonu i kakav rezultat dobijaš, bez lažnih
            readout kartica koje izgledaju klikabilno, a ništa ne rade.
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
              <div className="runtimepilot-advanced-summary-actions">
                {group.routes.map((route) => (
                  <button
                    type="button"
                    className="action-button-soft deck-control-button deck-control-button-secondary"
                    key={route.title}
                    onClick={() => route.onClick?.()}
                    disabled={!route.onClick}
                  >
                    <span className="runtimepilot-advanced-summary-action-copy">
                      <span className="runtimepilot-advanced-summary-action-title">{route.title}</span>
                      <span className="runtimepilot-advanced-summary-action-subtitle">
                        {route.subtitle}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
