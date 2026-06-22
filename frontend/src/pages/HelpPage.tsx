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
    title: "Početna",
    when: "Kad hoćeš najkraći pregled bez lutanja",
    detail: "Pet status kartica, aktivni model i telemetrija ti odmah kažu da li je sistem zdrav i koji je sledeći klik.",
    icon: "home",
  },
  {
    title: "Server",
    when: "Kad proveravaš runtime signal, health i pristup",
    detail: "Ovde su start, stop, restart, health URL, živi context i ručna dijagnostika ako runtime ne priča istu priču kao config.",
    icon: "server",
  },
  {
    title: "Modeli",
    when: "Kad biraš lokalni GGUF i aktivni runtime par",
    detail: "Ovde rešavaš lokalni katalog, aktivaciju, dodavanje sopstvenog GGUF-a i brzi skok na kompatibilnost.",
    icon: "models",
  },
  {
    title: "OpenCode",
    when: "Kad otvaraš pravi radni tok nad projektom",
    detail: "Sesija, managed config, poslednja akcija i napredni alati ovde govore da li je agent stvarno otvoren i vezan za aktivni model.",
    icon: "opencode",
  },
  {
    title: "Browser + Search + Znanje",
    when: "Kad tražiš model, izvor ili dokument pre rada",
    detail: "Browser služi za GGUF katalog, Search za veb trag, a Znanje za lokalne dokumente i knowledge-first tokove.",
    icon: "browser",
  },
  {
    title: "Kompatibilnost",
    when: "Kad proveravaš da li mašina stvarno nosi izabrani setup",
    detail: "Tu dobijaš procenu za runtime, VRAM, RAM, context i output, plus živo GPU stanje kad je dostupno.",
    icon: "compatibility",
  },
  {
    title: "Benchmark + Tuning Lab",
    when: "Kad meriš brzinu ili porediš stvarne slotove",
    detail: "Benchmark daje sirov throughput i istoriju, a Tuning Lab pravi stvaran task, diff i winner logiku za tri slota.",
    icon: "benchmark",
  },
  {
    title: "Podešavanja",
    when: "Kad menjaš profile, context, Search ili TurboQuant",
    detail: "Ovde su opšti editor, presetovi, Search provider, tema, TurboQuant parametri i primena sa jasnim readout signalom.",
    icon: "settings",
  },
  {
    title: "Napredno, Logovi i Servis",
    when: "Kad radiš dublju proveru ili održavanje",
    detail: "Napredno grupiše sekundarne tokove, Logovi čuvaju trag, a Repair i Updates služe kada sistem treba oporavak ili novu verziju.",
    icon: "repair",
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
        summary="Ovaj help centar prati sadašnji RuntimePilot raspored: Početna za brz signal, Server za runtime, Modeli za lokalni katalog, OpenCode za pravi rad i Napredno za dublje tokove."
        steps={[
          {
            title: "Prvo potvrdi health, runtime i aktivni model",
            detail: "Ako ove tri stvari nisu usklađene, skoro svaki sledeći ekran deluje kao kvar iako je uzrok već gore vidljiv.",
          },
          {
            title: "Zatim biraj: OpenCode za rad ili Benchmark/Tuning Lab za merenje",
            detail: "OpenCode je stvarni agent tok. Benchmark i Tuning Lab služe kada meriš, porediš ili tražiš pobednički profil.",
          },
          {
            title: "Kad zapne, idi na dijagnostiku umesto nasumičnog klikanja",
            detail: "Najčešći problemi su GPU fit, mismatch config/live context, loš Search provider signal ili sesija koja nije stvarno otvorena.",
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
              Ovaj ekran nije mrtav help tekst. Ispod odmah dobijaš brzu navigaciju, redosled rada,
              mapu ekrana i prvu dijagnostiku kada nešto ne izgleda logično.
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
          Ovo nije običan zid teksta. Svaka sekcija ima kratku namenu, jump link i praktične prečice
          do pravih delova aplikacije, usklađene sa sadašnjim headerom i hi-fi rasporedom stranica.
        </p>
        <div className="help-signal-strip">
          <span>Početna daje brzi signal, ali Server potvrđuje istinu.</span>
          <span>Browser i Kompatibilnost idu pre lokalne aktivacije kad tek biraš model.</span>
          <span>Tuning Lab koristi stvaran task, ne samo sirov benchmark.</span>
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
              <RuntimePilotIcon className="runtimepilot-nav-icon" name="home" />
            </span>
            <strong>1. Početna</strong>
            <p className="helper-text">Prvo pogledaj health, runtime, model, context i OpenCode signal u jednoj liniji.</p>
          </article>
          <span className="help-visual-arrow" aria-hidden="true">
            →
          </span>
          <article className="help-visual-step">
            <span className="help-visual-step-icon">
              <RuntimePilotIcon className="runtimepilot-nav-icon" name="server" />
            </span>
            <strong>2. Server + Modeli</strong>
            <p className="helper-text">Potvrdi runtime signal, pa aktiviraj model tek kad znaš da ga mašina može da nosi.</p>
          </article>
          <span className="help-visual-arrow" aria-hidden="true">
            →
          </span>
          <article className="help-visual-step">
            <span className="help-visual-step-icon">
              <RuntimePilotIcon className="runtimepilot-nav-icon" name="opencode" />
            </span>
            <strong>3. OpenCode / Benchmark / Tuning Lab</strong>
            <p className="helper-text">Tek tada idi na pravi rad, čisto merenje ili uporedne eksperimente.</p>
          </article>
        </div>
        <div className="help-checklist">
          <article className="help-checklist-item">
            <strong>Početna ti govori gde prvo da klikneš</strong>
            <p className="helper-text">
              Ako Početna kaže da je runtime ugašen, nema smisla odmah juriti Browser, OpenCode ili batch tokove.
            </p>
          </article>
          <article className="help-checklist-item">
            <strong>Browser i Kompatibilnost su put za nov model</strong>
            <p className="helper-text">
              Kad model još nije lokalno spreman, idi kroz Browser katalog i proveri fit pre nego što ga dodaš ili aktiviraš.
            </p>
          </article>
          <article className="help-checklist-item">
            <strong>OpenCode i Tuning Lab nisu ista stvar</strong>
            <p className="helper-text">
              OpenCode koristiš za stvaran rad nad projektom, a Tuning Lab kada želiš da isti zadatak pustiš kroz više slotova i dobiješ winner predlog.
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
        summary="Kada nemaš vremena da čitaš sve, kreni od ovih praktičnih tokova koji pokrivaju najčešće upotrebe sadašnjeg RuntimePilot-a."
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
            <strong>Nađi novi model bez slepog preuzimanja</strong>
            <p className="helper-text">
              Kada tek biraš model, idi redom: <strong>Browser → Kompatibilnost → Modeli</strong>. Tako prvo proveriš fit, pa tek onda praviš lokalni katalog.
            </p>
            <div className="inline-actions compact-actions">
              <button type="button" className="secondary-button" onClick={onOpenSearch}>
                Pretraga
              </button>
              <button type="button" className="secondary-button" onClick={onOpenSettings}>
                Kompatibilnost / Podešavanja
              </button>
              <button type="button" className="secondary-button" onClick={onOpenModels}>
                Modeli
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
            <strong>Nađi izvor pa tek onda pitaj model</strong>
            <p className="helper-text">
              Kada radiš knowledge-first tok, koristi <strong>Pretragu</strong> i lokalno <strong>Znanje</strong> pre nego što očekuješ da OpenCode sam pogodi pravi kontekst.
            </p>
            <div className="inline-actions compact-actions">
              <button type="button" className="secondary-button" onClick={onOpenSearch}>
                Pretraga
              </button>
              <button type="button" className="secondary-button" onClick={onOpenOpenCode}>
                OpenCode
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
        summary="Ovo je najkraće objašnjenje glavnih strana bez internog žargona i sa fokusom na trenutno važeći raspored aplikacije."
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
          <button type="button" className="secondary-button" onClick={onOpenServer}>
            Otvori Server
          </button>
          <button type="button" className="secondary-button" onClick={onOpenModels}>
            Otvori Modele
          </button>
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
        summary="Tuning Lab nije samo benchmark; on pokreće stvarni agent zadatak, success check, diff poređenje i winner logiku za tri slota."
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
            Ako ti ručni OpenCode uspe, a isti zadatak kroz Tuning Lab deluje čudno, gledaj success check,
            diff, poslednju poruku slota i aktivni run cockpit pre nego što zaključiš da je model loš.
          </p>
        </div>
      </HelpSectionCard>

      <HelpSectionCard
        id="troubleshooting"
        title="Rešavanje problema"
        summary="Ovo su prve stvari koje proveravaš kada nešto deluje sporo, nelogično, previše optimistično ili zaglavljeno."
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
        summary="Kratka objašnjenja za izraze koji se stalno pojavljuju kroz RuntimePilot, posebno kroz Compatibility, Settings i Tuning Lab."
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
