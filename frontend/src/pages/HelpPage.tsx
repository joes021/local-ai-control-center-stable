import type { ReactNode } from "react";

import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import { SupportPageDeck } from "../components/shell/SupportPageDeck";
import type { RuntimePilotIconName } from "../components/RuntimePilotIcon";

type HelpPageProps = {
  onOpenServer?: () => void;
  onOpenModels?: () => void;
  onOpenOpenCode?: () => void;
  onOpenBenchmark?: () => void;
  onOpenTuningLab?: () => void;
  onOpenSettings?: () => void;
  onOpenSearch?: () => void;
};

type HelpSection = {
  id: string;
  title: string;
  summary: string;
  icon: RuntimePilotIconName;
};

type HelpPageCard = {
  title: string;
  when: string;
  detail: string;
  icon: RuntimePilotIconName;
};

type TroubleshootingItem = {
  title: string;
  symptom: string;
  action: string;
  severity: "check" | "warn";
};

const HELP_SECTIONS: HelpSection[] = [
  {
    id: "quick-start",
    title: "Brzi početak",
    summary: "Najkraći put da pokreneš runtime, izabereš model i pređeš na pravi rad.",
    icon: "home",
  },
  {
    id: "pages",
    title: "Šta radi svaki tab",
    summary: "Kratko i ljudski objašnjenje glavnih delova RuntimePilot-a.",
    icon: "browser",
  },
  {
    id: "tuning-lab",
    title: "Tuning Lab i batch testovi",
    summary: "Kako porediti slotove, tumačiti pobednika i prepoznati lažno dobar rezultat.",
    icon: "tuning",
  },
  {
    id: "troubleshooting",
    title: "Rešavanje problema",
    summary: "Najčešći kvarovi i šta prvo da proveriš pre dubljeg čačkanja.",
    icon: "repair",
  },
  {
    id: "glossary",
    title: "Pojmovnik",
    summary: "Kratka objašnjenja za context, GPU layers, quant, offload i ostale izraze.",
    icon: "knowledge",
  },
];

const PAGE_GUIDES: HelpPageCard[] = [
  {
    title: "Server",
    when: "Kad proveravaš da li je runtime stvarno živ",
    detail: "Ovde vidiš start/stop/restart, CLI ekvivalente, health i da li config i živi proces pričaju istu priču.",
    icon: "server",
  },
  {
    title: "Modeli",
    when: "Kad biraš, preuzimaš ili aktiviraš model",
    detail: "Ovde rešavaš lokalne GGUF fajlove, kompatibilnost, aktivaciju i poreklo modela.",
    icon: "models",
  },
  {
    title: "OpenCode",
    when: "Kad radiš stvarni agent task nad projektom",
    detail: "Ovde su sesija, komande i živa veza sa agentom. To nije benchmark, nego pravi rad.",
    icon: "opencode",
  },
  {
    title: "Benchmark",
    when: "Kad meriš sirovu brzinu i upoređuješ tokene",
    detail: "Fokus je na throughput-u, istoriji merenja i čistim performansama runtime-a.",
    icon: "benchmark",
  },
  {
    title: "Tuning Lab",
    when: "Kad porediš podešavanja kroz stvarne zadatke",
    detail: "Ovde dobijaš queue, slotove, diff, success check i predlog pobednika.",
    icon: "tuning",
  },
  {
    title: "Podešavanja",
    when: "Kad juriš VRAM fit ili menjaš opštu kontrolu",
    detail: "Tu su opšta podešavanja, TurboQuant parametri i VRAM fit tokovi.",
    icon: "settings",
  },
];

const TROUBLESHOOTING_ITEMS: TroubleshootingItem[] = [
  {
    title: "GPU deluje slabo ili prazno",
    symptom: "CPU skače, VRAM deluje nizak, a model ipak radi.",
    action:
      "Idi na Server i proveri da li je GPU offload samo tražen ili stvarno potvrđen u runtime logu.",
    severity: "check",
  },
  {
    title: "Model ne staje u VRAM",
    symptom: "Režim pređe u hibrid ili RAM preliv ostane previsok.",
    action:
      "Idi na Podešavanja, otvori VRAM fit tuning i prvo smanji context pre agresivnijih runtime kompromisa.",
    severity: "warn",
  },
  {
    title: "Config i živi runtime se razilaze",
    symptom: "Sačuvana vrednost i živi proces pokazuju različit context ili runtime parametre.",
    action:
      "Kad vidiš mismatch između config i live stanja, restartuj runtime da nove vrednosti stvarno uđu u proces.",
    severity: "check",
  },
  {
    title: "Tuning Lab deluje tiho",
    symptom: "Run postoji, ali ne vidiš odmah promene ili ti deluje da se ništa ne dešava.",
    action:
      "Gledaj Aktivni run cockpit, PID-ove, workspace i live signal. Red čekanja znači redosled izvršavanja, ne paralelan rad.",
    severity: "warn",
  },
];

const GLOSSARY_ITEMS = [
  {
    term: "Context",
    detail:
      "Koliko tokena model drži u radnoj memoriji tokom razgovora. Veći context pomaže dužim zadacima, ali jače pritiska VRAM i RAM.",
  },
  {
    term: "GPU layers",
    detail:
      "Broj slojeva modela koji pokušavaju da žive na GPU-u. Više GPU slojeva znači manje RAM preliva i veći VRAM pritisak.",
  },
  {
    term: "Hybrid VRAM + RAM",
    detail:
      "Režim u kom deo modela ili cache-a živi u VRAM-u, a deo u sistemskom RAM-u. Radi, ali obično sporije od čistog GPU fit-a.",
  },
  {
    term: "Offload",
    detail:
      "Koliko je runtime stvarno prebacio na GPU. RuntimePilot razlikuje ono što je traženo u komandi od onoga što je log stvarno potvrdio.",
  },
  {
    term: "Quant",
    detail:
      "Kompresovana verzija modela. Manji quant obično troši manje memorije, ali može da utiče na kvalitet ili stabilnost odgovora.",
  },
  {
    term: "TurboQuant",
    detail:
      "Alternativni runtime put sa dodatnim parametrima za KV kompresiju i MoE ponašanje. Koristan je kada juriš bolji fit ili drugačiji balans brzine i memorije.",
  },
  {
    term: "Success check",
    detail:
      "Provera koja odlučuje da li je run stvarno uspeo. To može biti test, build, lint ili drugi jasan uslov koji si zadao.",
  },
  {
    term: "Tuning Lab winner",
    detail:
      "Predloženi pobednik među slotovima koji su uspešno završili zadatak i imali najbolji odnos trajanja, stabilnosti i telemetrije.",
  },
];

function HelpSectionCard({
  id,
  title,
  summary,
  icon,
  children,
}: {
  id: string;
  title: string;
  summary: string;
  icon: RuntimePilotIconName;
  children: ReactNode;
}) {
  return (
    <section className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module help-section-card" id={id}>
      <div className="section-header page-flow-header">
        <div className="runtimepilot-section-heading">
          <span className="runtimepilot-section-glyph">
            <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name={icon} />
          </span>
          <div>
            <span className="status-label">RuntimePilot help</span>
            <strong className="status-value">{title}</strong>
          </div>
        </div>
      </div>
      <p className="helper-text">{summary}</p>
      {children}
    </section>
  );
}

function HelpJumpStrip() {
  return (
    <div className="help-jump-strip">
      {HELP_SECTIONS.map((section) => (
        <a className="help-jump-pill" href={`#${section.id}`} key={section.id}>
          <span className="help-jump-pill-icon">
            <RuntimePilotIcon className="runtimepilot-nav-icon" name={section.icon} />
          </span>
          <span>{section.title}</span>
        </a>
      ))}
    </div>
  );
}

export function HelpPage({
  onOpenBenchmark,
  onOpenModels,
  onOpenOpenCode,
  onOpenSearch,
  onOpenServer,
  onOpenSettings,
  onOpenTuningLab,
}: HelpPageProps) {
  return (
    <div className="help-page runtimepilot-rack-page">
      <SupportPageDeck
        eyebrow="Pomoć"
        title="Najkraći put do rezultata"
        summary="Ovaj help centar je praktičan vodič kroz RuntimePilot. Ne objašnjava teoriju radi teorije, nego ti kaže gde da klikneš i šta da očekuješ."
        steps={[
          {
            title: "Pokreni runtime i proveri model",
            detail: "Ako runtime nije zdrav ili model nije aktivan, skoro sve dalje deluje kao da ne radi kako treba.",
          },
          {
            title: "Radi u OpenCode-u ili meri kroz Tuning Lab",
            detail: "OpenCode je za stvarni agent rad, a Tuning Lab za poređenje slotova i batch testove.",
          },
          {
            title: "Kad zapne, idi na Troubleshooting",
            detail: "Najčešći problemi su VRAM fit, GPU offload, mismatch config/live context i zaglavljeni agent tokovi.",
          },
        ]}
        actions={
          <>
            <button type="button" className="secondary-button" onClick={onOpenServer}>
              Otvori Server
            </button>
            <button type="button" className="secondary-button" onClick={onOpenModels}>
              Otvori Modele
            </button>
            <button type="button" className="secondary-button" onClick={onOpenOpenCode}>
              Otvori OpenCode
            </button>
            <button type="button" className="secondary-button" onClick={onOpenTuningLab}>
              Otvori Tuning Lab
            </button>
          </>
        }
        resultHint={
          <>
            <span className="status-label">Gde vidiš rezultat</span>
            <strong className="status-value">Jump linkovi i praktične sekcije odmah ispod</strong>
            <p className="helper-text">
              Ovaj ekran nije mrtav help tekst. Ispod odmah dobijaš brzu navigaciju, vizuelni redosled
              rada i prečice ka pravim tabovima.
            </p>
          </>
        }
      />
      <div className="help-hifi-stack">
      <div className="help-mixer-deck">

      <section className="status-card wide-card runtimepilot-section-shell runtimepilot-faceplate-module help-overview-shell">
        <div className="section-header page-flow-header">
          <div className="runtimepilot-section-heading">
            <span className="runtimepilot-section-glyph">
              <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="knowledge" />
            </span>
            <div>
              <span className="status-label">Sadržaj</span>
              <strong className="status-value">Brza navigacija kroz pomoć</strong>
            </div>
          </div>
        </div>
        <p className="helper-text">
          Ovo nije običan zid teksta. Svaka sekcija ima kratku namenu, jump link i praktične prečice do pravih delova aplikacije.
        </p>
        <div className="help-signal-strip">
          <span>Server prvo, pa model, pa agent rad.</span>
          <span>Tuning Lab koristi stvaran task, ne samo sirov benchmark.</span>
          <span>Troubleshooting je prečica do uzroka, ne poslednje utočište.</span>
        </div>
        <HelpJumpStrip />
        <div className="help-overview-grid">
          {HELP_SECTIONS.map((section) => (
            <a className="help-overview-card" href={`#${section.id}`} key={section.id}>
              <span className="help-overview-card-icon">
                <RuntimePilotIcon className="runtimepilot-nav-icon" name={section.icon} />
              </span>
              <strong>{section.title}</strong>
              <p className="helper-text">{section.summary}</p>
            </a>
          ))}
        </div>
      </section>

      <HelpSectionCard
        id="quick-start"
        title="Brzi početak"
        summary="Ako prvi put koristiš RuntimePilot, prati baš ovaj redosled i nemoj skakati između tabova bez potrebe."
        icon="home"
      >
        <div className="help-visual-workbench">
          <article className="help-visual-step">
            <span className="help-visual-step-icon">
              <RuntimePilotIcon className="runtimepilot-nav-icon" name="server" />
            </span>
            <strong>1. Server</strong>
            <p className="helper-text">Runtime mora da bude stvarno zdrav pre svega ostalog.</p>
          </article>
          <span className="help-visual-arrow" aria-hidden="true">
            →
          </span>
          <article className="help-visual-step">
            <span className="help-visual-step-icon">
              <RuntimePilotIcon className="runtimepilot-nav-icon" name="models" />
            </span>
            <strong>2. Modeli</strong>
            <p className="helper-text">Aktiviraj model tek kad znaš da ga mašina može da nosi.</p>
          </article>
          <span className="help-visual-arrow" aria-hidden="true">
            →
          </span>
          <article className="help-visual-step">
            <span className="help-visual-step-icon">
              <RuntimePilotIcon className="runtimepilot-nav-icon" name="opencode" />
            </span>
            <strong>3. OpenCode / Tuning Lab</strong>
            <p className="helper-text">Tek tada idi na pravi rad ili uporedne eksperimente.</p>
          </article>
        </div>
        <div className="help-checklist">
          <article className="help-checklist-item">
            <strong>Pokreni runtime i proveri model</strong>
            <p className="helper-text">
              Ovde odmah otkrivaš da li je problem u runtime-u, modelu ili samo u kasnijem toku rada.
            </p>
          </article>
          <article className="help-checklist-item">
            <strong>Izaberi radni put</strong>
            <p className="helper-text">
              OpenCode koristiš za stvarni agent rad, a Tuning Lab kada želiš poređenje slotova i winner logiku.
            </p>
          </article>
          <article className="help-checklist-item">
            <strong>Kad zapne, idi na pomoć za problem</strong>
            <p className="helper-text">
              Troubleshooting je tu da skrati lutanje, ne da bude poslednja stanica kada se već izgubiš.
            </p>
          </article>
        </div>
        <div className="inline-actions compact-actions">
          <button type="button" className="secondary-button" onClick={onOpenServer}>
            Idi na Server
          </button>
          <button type="button" className="secondary-button" onClick={onOpenModels}>
            Idi na Modele
          </button>
          <button type="button" className="secondary-button" onClick={onOpenOpenCode}>
            Idi na OpenCode
          </button>
          <button type="button" className="secondary-button" onClick={onOpenTuningLab}>
            Idi na Tuning Lab
          </button>
        </div>
      </HelpSectionCard>
      </div>

      <div className="help-transport-deck">
      <HelpSectionCard
        id="common-paths"
        title="Najčešći tokovi"
        summary="Kada nemaš vremena da čitaš sve, kreni od ovih tri najčešća praktična puta kroz RuntimePilot."
        icon="workflows"
      >
        <div className="help-path-grid">
          <article className="help-callout-card">
            <strong>Pokreni lokalni model za rad</strong>
            <p className="helper-text">
              Idi redom: <strong>Server → Modeli → OpenCode</strong>. Prvo proveri runtime, pa aktiviraj model, pa tek onda otvaraj agent rad.
            </p>
            <div className="inline-actions compact-actions">
              <button type="button" className="secondary-button" onClick={onOpenServer}>
                Server
              </button>
              <button type="button" className="secondary-button" onClick={onOpenModels}>
                Modeli
              </button>
              <button type="button" className="secondary-button" onClick={onOpenOpenCode}>
                OpenCode
              </button>
            </div>
          </article>
          <article className="help-callout-card">
            <strong>Poredi podešavanja kroz stvaran zadatak</strong>
            <p className="helper-text">
              Kada želiš da saznaš koji slot stvarno radi bolje, idi na <strong>Tuning Lab</strong>, učitaj batch i prati cockpit umesto da gledaš samo sirov benchmark throughput.
            </p>
            <div className="inline-actions compact-actions">
              <button type="button" className="secondary-button" onClick={onOpenTuningLab}>
                Tuning Lab
              </button>
              <button type="button" className="secondary-button" onClick={onOpenBenchmark}>
                Benchmark
              </button>
            </div>
          </article>
          <article className="help-callout-card">
            <strong>Nađi model i proveri da li staje</strong>
            <p className="helper-text">
              Kada nisi siguran šta mašina može da nosi, idi na <strong>Pretragu</strong> ili <strong>Modele</strong>, pa odmah proveri kompatibilnost pre aktivacije.
            </p>
            <div className="inline-actions compact-actions">
              <button type="button" className="secondary-button" onClick={onOpenSearch}>
                Pretraga
              </button>
              <button type="button" className="secondary-button" onClick={onOpenModels}>
                Modeli
              </button>
              <button type="button" className="secondary-button" onClick={onOpenSettings}>
                Podešavanja
              </button>
            </div>
          </article>
        </div>
      </HelpSectionCard>

      <HelpSectionCard
        id="pages"
        title="Šta radi svaki tab"
        summary="Ovo je najkraće objašnjenje glavnih strana bez internog žargona."
        icon="browser"
      >
        <div className="help-page-grid">
          {PAGE_GUIDES.map((item) => (
            <article className="help-page-card" key={item.title}>
              <div className="help-page-card-header">
                <span className="help-page-card-icon">
                  <RuntimePilotIcon className="runtimepilot-nav-icon" name={item.icon} />
                </span>
                <div>
                  <strong>{item.title}</strong>
                  <p className="helper-text">{item.when}</p>
                </div>
              </div>
              <p className="helper-text">{item.detail}</p>
            </article>
          ))}
        </div>
        <div className="inline-actions compact-actions">
          <button type="button" className="secondary-button" onClick={onOpenBenchmark}>
            Otvori Benchmark
          </button>
          <button type="button" className="secondary-button" onClick={onOpenSettings}>
            Otvori Podešavanja
          </button>
          <button type="button" className="secondary-button" onClick={onOpenSearch}>
            Otvori Pretragu
          </button>
        </div>
      </HelpSectionCard>
      </div>

      <div className="help-monitor-deck">
      <HelpSectionCard
        id="tuning-lab"
        title="Tuning Lab i batch testovi"
        summary="Tuning Lab nije samo benchmark; on pokreće stvarni agent zadatak, success check i diff poređenje."
        icon="tuning"
      >
        <div className="help-callout-grid">
          <article className="help-callout-card">
            <strong>Jedan run nije isto što i benchmark</strong>
            <p className="helper-text">
              `Output tok/s` u Tuning Lab-u može biti niži od čistog benchmark-a jer agent čita, piše fajlove i vrti success check.
            </p>
          </article>
          <article className="help-callout-card">
            <strong>Pobednik nije samo najbrži</strong>
            <p className="helper-text">
              Winner mora i da završi zadatak i da prođe success check. Brzina sama po sebi nije dovoljna.
            </p>
          </article>
          <article className="help-callout-card">
            <strong>Batch ide redom, ne paralelno</strong>
            <p className="helper-text">
              Red čekanja znači da su taskovi zadati, ali se izvršavaju sekvencijalno: jedan run po jedan, jedan slot po jedan.
            </p>
          </article>
        </div>
        <div className="help-inline-note">
          <span className="help-inline-note-icon">
            <RuntimePilotIcon className="runtimepilot-nav-icon" name="observability" />
          </span>
          <p className="helper-text">
            Ako ti ručni OpenCode uspe, a isti zadatak kroz Tuning Lab deluje čudno, gledaj success check, diff i aktivni slot signal pre nego što zaključiš da je model loš.
          </p>
        </div>
      </HelpSectionCard>

      <HelpSectionCard
        id="troubleshooting"
        title="Rešavanje problema"
        summary="Ovo su prve stvari koje proveravaš kada nešto deluje sporo, nelogično ili zaglavljeno."
        icon="repair"
      >
        <div className="help-troubleshooting-list">
          {TROUBLESHOOTING_ITEMS.map((item) => (
            <article className="help-troubleshooting-item" key={item.title}>
              <div className="help-troubleshooting-item-header">
                <strong>{item.title}</strong>
                <span
                  className={`help-severity-badge ${
                    item.severity === "warn" ? "help-severity-badge-warn" : "help-severity-badge-check"
                  }`}
                >
                  {item.severity === "warn" ? "Visok prioritet" : "Brza dijagnostika"}
                </span>
              </div>
              <p className="helper-text">
                <strong>Signal:</strong> {item.symptom}
              </p>
              <p className="helper-text">
                <strong>Prvi korak:</strong> {item.action}
              </p>
            </article>
          ))}
        </div>
      </HelpSectionCard>

      <HelpSectionCard
        id="glossary"
        title="Pojmovnik"
        summary="Kratka objašnjenja za izraze koji se stalno pojavljuju kroz RuntimePilot."
        icon="knowledge"
      >
        <div className="help-glossary-grid">
          {GLOSSARY_ITEMS.map((item) => (
            <article className="help-glossary-card" key={item.term}>
              <strong>{item.term}</strong>
              <p className="helper-text">{item.detail}</p>
            </article>
          ))}
        </div>
      </HelpSectionCard>
      </div>
      </div>
    </div>
  );
}
