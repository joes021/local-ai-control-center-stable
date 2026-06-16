import { useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageFlowCard } from "../components/PageFlowCard";
import {
  RuntimePilotActionDeck,
  type RuntimePilotActionDeckItem,
} from "../components/shell/RuntimePilotActionDeck";
import {
  RuntimePilotStatusDeck,
  type RuntimePilotStatusDeckItem,
} from "../components/shell/RuntimePilotStatusDeck";
import { runRepair } from "../lib/api";
import type { ActionResult } from "../lib/types";

type RepairResult = ActionResult & {
  repairKind?: string;
  title?: string;
  userMessage?: string;
  nextStep?: string;
  safeForNonTechnicalUsers?: boolean;
};

function repairKindLabel(kind: string) {
  switch (kind) {
    case "install":
      return "instalacija";
    case "model":
      return "model";
    case "runtime":
      return "runtime";
    case "config":
      return "podešavanja";
    default:
      return kind || "servis";
  }
}

export function RepairPage() {
  const [result, setResult] = useState<RepairResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyKind, setBusyKind] = useState<string>("");

  function scrollToResult() {
    document.getElementById("repair-action-result")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }

  function triggerRepair(kind: string) {
    setBusyKind(kind);
    setError(null);
    void runRepair(kind)
      .then((payload) => setResult(payload as RepairResult))
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : "Popravka nije uspela.");
      })
      .finally(() => {
        setBusyKind("");
      });
  }

  const repairStatusItems: RuntimePilotStatusDeckItem[] = [
    {
      id: "repair-flow",
      label: "Servisni tok",
      value: busyKind ? `Pokreće ${repairKindLabel(busyKind)}` : "Bezbedan servisni tok",
      detail: busyKind
        ? "Pokrenuta je samo jedna popravka i čeka se jasan rezultat."
        : "Ovde uvek ide jedna po jedna akcija da korisnik odmah zna šta se desilo.",
      action: "Jedna akcija",
      icon: "repair",
      accent: "rgba(242, 184, 75, 0.34)",
    },
    {
      id: "repair-result",
      label: "Rezultat",
      value: result?.title ?? (error ? "Greška pri servisu" : "Čeka izbor"),
      detail:
        result?.userMessage ||
        error ||
        "Kada pokreneš popravku, ovde prvo vidiš kratko objašnjenje bez ulaska u detaljni log.",
      action: "Kratko objašnjenje",
      icon: "control",
      accent: "rgba(109, 172, 255, 0.34)",
    },
    {
      id: "repair-next",
      label: "Sledeći korak",
      value: result?.nextStep ? "Predlog spreman" : "Čeka rezultat",
      detail:
        result?.nextStep ||
        "Posle završetka ovde dolazi sledeći korak, tako da korisnik ne nagađa šta dalje.",
      action: "Jasna preporuka",
      icon: "workflows",
      accent: "rgba(88, 222, 193, 0.34)",
    },
    {
      id: "repair-panel",
      label: "Detalji",
      value: "ActionResultPanel",
      detail: "Ako kratka poruka nije dovoljna, skok vodi pravo na puni rezultat i servisni izlaz.",
      action: "Skok na rezultat",
      icon: "logs",
      accent: "rgba(255, 129, 177, 0.34)",
      onClick: scrollToResult,
    },
  ];

  const repairActionItems: RuntimePilotActionDeckItem[] = [
    {
      id: "repair-install",
      code: "INS",
      title: "Popravka instalacije",
      subtitle: "FAJLOVI + PUTANJE",
      icon: "repair",
      detail: "Koristi kada je portal oštećen, launcher nestao ili installer fajlovi deluju nepotpuno.",
      disabled: Boolean(busyKind),
      tone: "primary",
      onClick: () => triggerRepair("install"),
    },
    {
      id: "repair-model",
      code: "MOD",
      title: "Popravka modela",
      subtitle: "MODEL + KATALOG",
      icon: "models",
      detail: "Za aktivni model, lokalni katalog i slučajeve kada izbor modela deluje razvezano.",
      disabled: Boolean(busyKind),
      onClick: () => triggerRepair("model"),
    },
    {
      id: "repair-runtime",
      code: "RUN",
      title: "Popravka runtime-a",
      subtitle: "ENGINE + HEALTH",
      icon: "runtime",
      detail: "Koristi kada health, port ili veza sa runtime-om ne deluju stabilno.",
      disabled: Boolean(busyKind),
      onClick: () => triggerRepair("runtime"),
    },
    {
      id: "repair-config",
      code: "CFG",
      title: "Popravka podešavanja",
      subtitle: "PROFIL + KONFIG",
      icon: "settings",
      detail: "Za profile, context, output i druga podešavanja koja su ostala u lošem stanju.",
      disabled: Boolean(busyKind),
      onClick: () => triggerRepair("config"),
    },
    {
      id: "repair-result-jump",
      code: "LOG",
      title: "Skok na rezultat",
      subtitle: "ISHOD + DETALJI",
      icon: "logs",
      detail: "Posle svake popravke prvo pročitaj sažetak i sledeći korak u donjem panelu.",
      onClick: scrollToResult,
    },
  ];

  return (
    <>
      {error ? <div className="error-panel wide-card">{error}</div> : null}

      <PageFlowCard
        title="Repair tok"
        summary="Ovde prvo izabereš vrstu popravke, zatim sačekaš jasan rezultat, pa pratiš sledeći korak koji RuntimePilot predloži."
        steps={[
          {
            title: "Izaberi jednu vrstu problema",
            detail: "Ne pokreći više popravki odjednom; najčistije je da prvo zaključaš da li je problem u instalaciji, modelu, runtime-u ili podešavanjima.",
          },
          {
            title: "Sačekaj završetak i poruku",
            detail: "Repair je zamišljen za netehnički tok: jedna akcija, jedan rezultat, jedan naredni korak.",
          },
          {
            title: "Tek onda proveri detalje",
            detail: "Ako kratko objašnjenje nije dovoljno, ActionResultPanel ostaje tu za dublji uvid u izlaz popravke.",
          },
        ]}
      />

      <RuntimePilotStatusDeck
        eyebrow="Servisni signal"
        title="Bezbedan servisni tok"
        helper="Četiri karte odmah pokazuju da li je popravka pokrenuta, šta je poslednji ishod, koji je sledeći korak i gde su detalji."
        items={repairStatusItems}
      />

      <RuntimePilotActionDeck
        eyebrow="Akcije"
        title="Izaberi jednu vrstu popravke"
        helper="Sve glavne popravke su ovde kao stvarne komande: instalacija, model, runtime, podešavanja i skok na ishod."
        items={repairActionItems}
      />

      <section className="status-card wide-card runtimepilot-faceplate-module">
        <div className="runtimepilot-inline-heading">
          <span className="status-label">Kratko objašnjenje</span>
          <strong className="status-value">
            Ako nešto nije u redu, ovde pokrećeš jednu jasnu i bezbednu popravku.
          </strong>
        </div>
        <p className="helper-text">
          Ovaj tok je namenjen netehničkim korisnicima: izaberi šta želiš da popraviš, sačekaj rezultat, pa prati sledeći korak koji ti aplikacija prikaže.
        </p>
        <div className="summary-metrics">
          <span>Aktivna akcija: {busyKind ? repairKindLabel(busyKind) : "nema"}</span>
          <span>Poslednji status: {result?.status || "--"}</span>
          <span>Bezbedan tok: {result?.safeForNonTechnicalUsers === false ? "proveri detalje" : "da"}</span>
        </div>
      </section>

      <div id="repair-action-result" className="wide-card runtimepilot-service-anchor">
        {result ? (
          <section className="status-card wide-card runtimepilot-faceplate-module">
            <div className="runtimepilot-inline-heading">
              <span className="status-label">{result.title ?? "Rezultat popravke"}</span>
              <strong className="status-value">{result.userMessage ?? result.summary}</strong>
            </div>
            <p className="helper-text">
              <strong>Sledeći korak:</strong>{" "}
              {result.nextStep ?? "Otvorite Detalji ako želite više informacija."}
            </p>
          </section>
        ) : null}
        <ActionResultPanel result={result} />
      </div>
    </>
  );
}
