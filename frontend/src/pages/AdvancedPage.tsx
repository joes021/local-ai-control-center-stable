import { HomeHiFiCommandButton } from "../components/home/HomeHiFiCommandButton";
import { HomeHiFiModule } from "../components/home/HomeHiFiModule";
import type { HomeHiFiSignalItem } from "../components/home/HomeHiFiSignalRail";
import type { RuntimePilotIconName } from "../components/RuntimePilotIcon";
import { PageFlowCard } from "../components/PageFlowCard";

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

type AdvancedAction = {
  title: string;
  subtitle: string;
  code: string;
  icon: RuntimePilotIconName;
  onClick?: () => void;
};

type AdvancedDisplayCard = {
  label: string;
  value: string;
  detail: string;
};

type AdvancedFooterCard = {
  label: string;
  value: string;
  detail: string;
};

type AdvancedSection = {
  tone: "analysis" | "knowledge" | "control" | "service";
  eyebrow: string;
  title: string;
  badge: string;
  summaryTitle: string;
  summaryText: string;
  railItems: HomeHiFiSignalItem[];
  readouts: AdvancedDisplayCard[];
  footer: AdvancedFooterCard[];
  actions: AdvancedAction[];
};

function renderActions(actions: readonly AdvancedAction[]) {
  return actions.map((action, index) => (
    <HomeHiFiCommandButton
      key={action.title}
      code={action.code}
      title={action.title}
      subtitle={action.subtitle}
      icon={action.icon}
      tone={index === 0 ? "primary" : "default"}
      disabled={!action.onClick}
      onClick={() => action.onClick?.()}
    />
  ));
}

export function AdvancedPage({
  onOpenBenchmark,
  onOpenBrowser,
  onOpenTuningLab,
  onOpenCompatibility,
  onOpenObservability,
  onOpenKnowledge,
  onOpenSearch,
  onOpenWorkflows,
  onOpenProjectMemory,
  onOpenSettings,
  onOpenLogs,
  onOpenHelp,
  onOpenRepair,
  onOpenUpdates,
  onOpenFleet,
  onOpenJobs,
}: AdvancedPageProps) {
  const sections: AdvancedSection[] = [
    {
      tone: "analysis",
      eyebrow: "Veliki modul 4",
      title: "Analiza i tuning",
      badge: "Prvo izmeri, pa menjaj",
      summaryTitle: "Meri, uporedi i potvrdi pre nego što diraš profil.",
      summaryText:
        "Benchmark, Tuning Lab, kompatibilnost i telemetrija drže odluku na brojevima umesto na utisku.",
      railItems: [
        {
          label: "Signal",
          value: "Meri pre odluke",
          detail: "Throughput, batch i fit moraju prvo da se potvrde.",
          tone: "signal",
        },
        {
          label: "Ishod",
          value: "Jasan winner",
          detail: "Odmah vidiš šta ostaje, a šta otpada.",
          tone: "accent",
        },
        {
          label: "Tip toka",
          value: "Benchmark → Lab → Fit",
          detail: "Merenje, task i potvrda na živom runtime-u.",
          tone: "success",
        },
      ],
      readouts: [
        {
          label: "Šta vidiš ovde",
          value: "Test, slot i fit",
          detail: "Brzina, task slotovi i VRAM potvrda na jednom mestu.",
        },
        {
          label: "Glavni rezultat",
          value: "Winner ostaje vidljiv",
          detail: "Ne vraćaš se nazad da tražiš brojke i zaključak.",
        },
        {
          label: "Zašto je ovde",
          value: "Pre svake veće promene",
          detail: "Prvo potvrdi da nova kombinacija stvarno vredi.",
        },
      ],
      footer: [
        {
          label: "Brzina",
          value: "Benchmark",
          detail: "Poređenje kroz više run-ova.",
        },
        {
          label: "Task",
          value: "Tuning Lab",
          detail: "Tri slota i winner logika.",
        },
        {
          label: "Fit",
          value: "Kompatibilnost",
          detail: "VRAM, context i primena.",
        },
        {
          label: "Live",
          value: "Telemetrija",
          detail: "GPU puls i živi signal.",
        },
      ],
      actions: [
        {
          title: "Otvori Benchmark",
          subtitle: "BRZINA + ISTORIJA",
          code: "BNCH",
          icon: "benchmark",
          onClick: onOpenBenchmark,
        },
        {
          title: "Otvori Tuning Lab",
          subtitle: "TRI SLOTA + TASK",
          code: "LAB",
          icon: "tuning",
          onClick: onOpenTuningLab,
        },
        {
          title: "Otvori kompatibilnost",
          subtitle: "VRAM FIT + KONTEKST",
          code: "FIT",
          icon: "compatibility",
          onClick: onOpenCompatibility,
        },
        {
          title: "Otvori telemetriju",
          subtitle: "ŽIVI SIGNAL + GPU",
          code: "LIVE",
          icon: "observability",
          onClick: onOpenObservability,
        },
      ],
    },
    {
      tone: "knowledge",
      eyebrow: "Veliki modul 5",
      title: "Znanje i istraživanje",
      badge: "Prvo izvor, pa pitanje",
      summaryTitle: "Nađi pravi model, dokument ili izvor pre rada.",
      summaryText:
        "Katalog, znanje, pretraga i radni tokovi daju čist ulaz pre nego što agent krene da radi.",
      railItems: [
        {
          label: "Signal",
          value: "Ulaz pre rada",
          detail: "Prvo biraš izvor, pa tek onda pitaš.",
          tone: "signal",
        },
        {
          label: "Ishod",
          value: "Izvor je usidren",
          detail: "Model, dokument ili web trag postaje konkretan ulaz.",
          tone: "accent",
        },
        {
          label: "Tip toka",
          value: "Katalog → Znanje → Tok",
          detail: "Nađi izvor, usidri ga i pretvori u rad.",
          tone: "success",
        },
      ],
      readouts: [
        {
          label: "Šta vidiš ovde",
          value: "Izvor i kontekst",
          detail: "Katalog, dokumenti, pretraga i preset tokovi.",
        },
        {
          label: "Glavni rezultat",
          value: "Bolji ulaz za agenta",
          detail: "Manje lutanja, više konkretnog rada i manje praznih pokušaja.",
        },
        {
          label: "Zašto je ovde",
          value: "Pre otvaranja taska",
          detail: "Prvo proveri izvor kad nisi siguran odakle da kreneš.",
        },
      ],
      footer: [
        {
          label: "Katalog",
          value: "Browser",
          detail: "Modeli i izvorne stranice.",
        },
        {
          label: "Dokumenti",
          value: "Znanje",
          detail: "Lokalni sadržaj i rad nad tekstom.",
        },
        {
          label: "Izvori",
          value: "Pretraga",
          detail: "Web plus lokalno.",
        },
        {
          label: "Preset",
          value: "Radni tokovi",
          detail: "Ponovljivi scenariji.",
        },
      ],
      actions: [
        {
          title: "Otvori Browser katalog",
          subtitle: "MODELI + IZVORI",
          code: "CAT",
          icon: "browser",
          onClick: onOpenBrowser,
        },
        {
          title: "Otvori Znanje",
          subtitle: "DOKUMENTI + ZNANJE",
          code: "DOC",
          icon: "knowledge",
          onClick: onOpenKnowledge,
        },
        {
          title: "Otvori Pretragu",
          subtitle: "WEB + LOKALNO",
          code: "SRC",
          icon: "search",
          onClick: onOpenSearch,
        },
        {
          title: "Otvori Radne tokove",
          subtitle: "PRESET + TOK",
          code: "FLOW",
          icon: "workflows",
          onClick: onOpenWorkflows,
        },
      ],
    },
    {
      tone: "control",
      eyebrow: "Veliki modul 6",
      title: "Fokus i konfiguracija",
      badge: "Fokus, podešavanja i tragovi",
      summaryTitle: "Cilj projekta, aktivne vrednosti i logovi moraju biti jasni.",
      summaryText:
        "Ovde čuvaš fokus, menjaš profile i odmah vidiš trag kada nešto zastane.",
      railItems: [
        {
          label: "Signal",
          value: "Red u projektu",
          detail: "Cilj, pravila i sledeći korak ostaju vidljivi.",
          tone: "signal",
        },
        {
          label: "Ishod",
          value: "Jasno stanje sistema",
          detail: "Podešavanja i logovi brzo pokažu šta je aktivno.",
          tone: "accent",
        },
        {
          label: "Tip toka",
          value: "Memory → Podeš. → Log",
          detail: "Fokus, vrednosti i trag u istom bay-u.",
          tone: "success",
        },
      ],
      readouts: [
        {
          label: "Šta vidiš ovde",
          value: "Fokus i kontrola",
          detail: "Project Memory, podešavanja, logovi i pomoć.",
        },
        {
          label: "Glavni rezultat",
          value: "Agent ne gubi cilj",
          detail: "Profil i tragovi ostaju na jednom mestu dok rad traje.",
        },
        {
          label: "Zašto je ovde",
          value: "Kad rad traje dugo",
          detail: "Jasna memorija i čisti logovi čuvaju kontinuitet.",
        },
      ],
      footer: [
        {
          label: "Fokus",
          value: "Project Memory",
          detail: "Cilj, pravila i naredni koraci.",
        },
        {
          label: "Podeš.",
          value: "Podešavanja",
          detail: "Profil, context i runtime parametri.",
        },
        {
          label: "Trag",
          value: "Logovi",
          detail: "Šta je puklo ili zastalo.",
        },
        {
          label: "Pomoć",
          value: "Help",
          detail: "Vođeni sledeći koraci.",
        },
      ],
      actions: [
        {
          title: "Otvori Project Memory",
          subtitle: "CILJ + PRAVILA",
          code: "MEM",
          icon: "memory",
          onClick: onOpenProjectMemory,
        },
        {
          title: "Otvori Podešavanja",
          subtitle: "PROFIL + CONTEXT",
          code: "CFG",
          icon: "settings",
          onClick: onOpenSettings,
        },
        {
          title: "Otvori Logove",
          subtitle: "TRAG + PORUKE",
          code: "LOG",
          icon: "logs",
          onClick: onOpenLogs,
        },
        {
          title: "Otvori Pomoć",
          subtitle: "VODIČ + POMOĆ",
          code: "HELP",
          icon: "help",
          onClick: onOpenHelp,
        },
      ],
    },
    {
      tone: "service",
      eyebrow: "Veliki modul 7",
      title: "Servis i verzije",
      badge: "Servis, update i verzije",
      summaryTitle: "Vrati sistem u zdravo stanje i isprati ga do kraja.",
      summaryText:
        "Popravka, ažuriranja, flota i redovi poslova žive odvojeno od glavnog toka, ali ostaju na jedan klik.",
      railItems: [
        {
          label: "Signal",
          value: "Servisni tok",
          detail: "Popravka i release imaju svoj jasan panel.",
          tone: "signal",
        },
        {
          label: "Ishod",
          value: "Kontrolisan oporavak",
          detail: "Odmah vidiš da li ideš na fix, update, flotu ili red.",
          tone: "accent",
        },
        {
          label: "Tip toka",
          value: "Repair → Update → Jobs",
          detail: "Vrati stanje, potvrdi verziju i isprati tok.",
          tone: "success",
        },
      ],
      readouts: [
        {
          label: "Šta vidiš ovde",
          value: "Servis i release",
          detail: "Oporavak, verzije, dodatne mašine i poslovi.",
        },
        {
          label: "Glavni rezultat",
          value: "Nema sakrivenih alata",
          detail: "Ređi tokovi su odvojeni, ali i dalje jasni i direktni.",
        },
        {
          label: "Zašto je ovde",
          value: "Kad sistem traži održavanje",
          detail: "Ne guši početnu stranu, ali ostaje spremno na klik.",
        },
      ],
      footer: [
        {
          label: "Fix",
          value: "Popravka",
          detail: "Oporavak i servisni tokovi.",
        },
        {
          label: "Release",
          value: "Ažuriranja",
          detail: "Verzije i sledeći korak.",
        },
        {
          label: "Mreža",
          value: "Flota",
          detail: "Dodatne mašine i širi pogled.",
        },
        {
          label: "Red",
          value: "Poslovi",
          detail: "Duži tokovi i queue status.",
        },
      ],
      actions: [
        {
          title: "Otvori Popravku",
          subtitle: "POPRAVKA + SERVIS",
          code: "FIX",
          icon: "repair",
          onClick: onOpenRepair,
        },
        {
          title: "Otvori Ažuriranja",
          subtitle: "RELEASE + VERZIJE",
          code: "UPD",
          icon: "updates",
          onClick: onOpenUpdates,
        },
        {
          title: "Otvori Flotu",
          subtitle: "MREŽA + PREGLED",
          code: "NODE",
          icon: "fleet",
          onClick: onOpenFleet,
        },
        {
          title: "Otvori Poslove",
          subtitle: "RED + PRAĆENJE",
          code: "JOB",
          icon: "jobs",
          onClick: onOpenJobs,
        },
      ],
    },
  ];

  return (
    <>
      <PageFlowCard
        title="Sekundarni hub"
        summary="Kad glavni tok već radi, ovde ulaziš u analizu, istraživanje, konfiguraciju i servis bez gušenja početne strane."
        steps={[
          {
            title: "Izaberi modul",
            detail: "Prvo odluči da li ti treba analiza, izvor, konfiguracija ili servis.",
          },
          {
            title: "Otvori alat",
            detail: "Svako veliko dugme vodi direktno na pravi ekran, bez mrtvih kartica.",
          },
          {
            title: "Vrati se u hub",
            detail: "Napredno ostaje zajednički hi-fi panel za sledeći korak.",
          },
        ]}
      />

      <div className="advanced-rack-stack wide-card">
        {sections.map((section) => (
          <HomeHiFiModule
            key={section.title}
            className={`advanced-rack-module advanced-rack-module-${section.tone}`}
            variant="runtime-primary"
            eyebrow={section.eyebrow}
            title={section.title}
            headerBadge={<span className="runtimepilot-home-guidance-pill">{section.badge}</span>}
            railItems={section.railItems}
            summaryTitle={section.summaryTitle}
            summaryText={section.summaryText}
            readouts={section.readouts}
            actions={renderActions(section.actions)}
            footer={section.footer}
          />
        ))}
      </div>
    </>
  );
}
