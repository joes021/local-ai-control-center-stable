import { useEffect, useMemo, useState } from "react";

import { ActionResultPanel } from "../components/ActionResultPanel";
import { PageDataStateCard } from "../components/PageDataStateCard";
import { PageFlowCard } from "../components/PageFlowCard";
import { RuntimePilotIcon } from "../components/RuntimePilotIcon";
import { saveProjectMemory, seedProjectMemory } from "../lib/api";
import type {
  ActionResult,
  ProjectMemoryItem,
  ProjectMemoryPayload,
  ProjectMemorySavePayload,
} from "../lib/types";

type ProjectMemoryPageProps = {
  memory: ProjectMemoryPayload | null;
  loading: boolean;
  error?: string | null;
  onMemoryChange: (payload: ProjectMemoryPayload) => void;
  onRefresh?: () => Promise<void> | void;
  onOpenTuningLab?: () => void;
};

type MemoryListEditorProps = {
  title: string;
  summary: string;
  items: ProjectMemoryItem[];
  emptyText: string;
  allowLock?: boolean;
  onChange: (items: ProjectMemoryItem[]) => void;
};

function createMemoryItem(prefix: string): ProjectMemoryItem {
  return {
    id: `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    text: "",
    locked: false,
  };
}

function cloneMemoryToDraft(memory: ProjectMemoryPayload): ProjectMemorySavePayload {
  return {
    goal: { ...memory.goal },
    rules: memory.rules.map((item) => ({ ...item })),
    decisions: memory.decisions.map((item) => ({ ...item })),
    progress: memory.progress.map((item) => ({ ...item })),
    nextSteps: memory.nextSteps.map((item) => ({ ...item })),
  };
}

function MemoryListEditor({
  title,
  summary,
  items,
  emptyText,
  allowLock = false,
  onChange,
}: MemoryListEditorProps) {
  return (
    <section className="status-card project-memory-editor-card runtimepilot-section-shell">
      <div className="section-header page-flow-header">
        <div className="runtimepilot-section-heading">
          <span className="runtimepilot-section-glyph">
            <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="memory" />
          </span>
          <div>
            <span className="status-label">Project Memory</span>
            <strong className="status-value">{title}</strong>
          </div>
        </div>
        <div className="inline-actions compact-actions">
          <button
            type="button"
            onClick={() => onChange([...items, createMemoryItem(title.toLowerCase().replace(/\s+/g, "-"))])}
          >
            Dodaj stavku
          </button>
        </div>
      </div>
      <p className="helper-text">{summary}</p>
      <div className="project-memory-list">
        {items.length ? (
          items.map((item, index) => (
            <div className="project-memory-item-row" key={item.id}>
              <div className="project-memory-item-field">
                <span className="project-memory-item-index">{index + 1}</span>
                <input
                  type="text"
                  value={item.text}
                  placeholder={emptyText}
                  onChange={(event) => {
                    const nextItems = items.map((current) =>
                      current.id === item.id ? { ...current, text: event.target.value } : current,
                    );
                    onChange(nextItems);
                  }}
                />
              </div>
              {allowLock ? (
                <label className="project-memory-lock-toggle">
                  <input
                    type="checkbox"
                    checked={Boolean(item.locked)}
                    onChange={(event) => {
                      const nextItems = items.map((current) =>
                        current.id === item.id ? { ...current, locked: event.target.checked } : current,
                      );
                      onChange(nextItems);
                    }}
                  />
                  <span>Zaključaj</span>
                </label>
              ) : null}
              <button
                type="button"
                className="secondary-button"
                onClick={() => onChange(items.filter((current) => current.id !== item.id))}
              >
                Ukloni
              </button>
            </div>
          ))
        ) : (
          <p className="helper-text">{emptyText}</p>
        )}
      </div>
    </section>
  );
}

export function ProjectMemoryPage({
  memory,
  loading,
  error,
  onMemoryChange,
  onRefresh,
  onOpenTuningLab,
}: ProjectMemoryPageProps) {
  const [draft, setDraft] = useState<ProjectMemorySavePayload | null>(null);
  const [seedGoal, setSeedGoal] = useState("");
  const [seedTaskPrompt, setSeedTaskPrompt] = useState("");
  const [result, setResult] = useState<ActionResult | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (!memory || isDirty) {
      return;
    }
    setDraft(cloneMemoryToDraft(memory));
    setSeedGoal((current) => current || memory.goal.text);
  }, [memory, isDirty]);

  const counts = useMemo(() => {
    if (!draft) {
      return null;
    }
    return {
      rules: draft.rules.filter((item) => item.text.trim()).length,
      decisions: draft.decisions.filter((item) => item.text.trim()).length,
      progress: draft.progress.filter((item) => item.text.trim()).length,
      nextSteps: draft.nextSteps.filter((item) => item.text.trim()).length,
    };
  }, [draft]);

  if (loading && !memory) {
    return <PageDataStateCard loadingText="Učitavam Project Memory..." />;
  }

  if ((!memory && !draft) || !draft) {
    return (
      <PageDataStateCard
        loadingText="Project Memory trenutno nije spreman."
        error={error || "Project Memory trenutno nije dostupan."}
        onRetry={onRefresh ? () => void onRefresh() : undefined}
      />
    );
  }

  const lastUpdatedLabel = memory?.updatedAt
    ? new Date(memory.updatedAt).toLocaleString("sr-RS")
    : "još nije sačuvano";

  return (
    <>
      <PageFlowCard
        title="Jedna radna memorija za cilj, pravila i sledeći korak"
        summary="Project Memory čuva fokus projekta van samog prompta. Time agent i korisnik imaju jednu istu, vidljivu istinu o tome šta se radi, šta je već odlučeno i šta sledi."
        steps={[
          {
            title: "Posej početni fokus",
            detail: "Unesi glavni cilj i, po potrebi, task tekst. Sistem će predložiti pravila i sledeći korak.",
          },
          {
            title: "Zaključaj ono što agent ne sme da promeni",
            detail: "Cilj i važna pravila mogu da se zaključaju da fokus ostane stabilan i kroz duže run-ove.",
          },
          {
            title: "Održavaj napredak kratko i jasno",
            detail: "Dodaj šta je gotovo i šta sledi, umesto da pokušavaš da sve pamtiš kroz dugačak prompt ili istoriju četa.",
          },
        ]}
        actions={
          <>
            {onOpenTuningLab ? (
              <button type="button" onClick={onOpenTuningLab}>
                Otvori Tuning Lab
              </button>
            ) : null}
            {onRefresh ? (
              <button type="button" onClick={() => void onRefresh()}>
                Osveži sa diska
              </button>
            ) : null}
          </>
        }
      />

      <section className="status-card wide-card runtimepilot-section-shell project-memory-seed-card">
        <div className="section-header page-flow-header">
          <div className="runtimepilot-section-heading">
            <span className="runtimepilot-section-glyph">
              <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="memory" />
            </span>
            <div>
              <span className="status-label">Starter extraction</span>
              <strong className="status-value">Posej memoriju iz cilja i task teksta</strong>
            </div>
          </div>
          <div className="inline-actions compact-actions">
            <button
              type="button"
              className="action-button-soft"
              disabled={isSeeding || !seedGoal.trim() || !seedTaskPrompt.trim()}
              onClick={async () => {
                setIsSeeding(true);
                try {
                  const seeded = await seedProjectMemory({
                    goal: seedGoal,
                    taskPrompt: seedTaskPrompt,
                  });
                  onMemoryChange(seeded);
                  setDraft(cloneMemoryToDraft(seeded));
                  setIsDirty(false);
                  setResult({
                    status: "ok",
                    action: "seed-project-memory",
                    summary: "Project Memory je posejan iz cilja i task teksta.",
                    details: {
                      returncode: 0,
                      stdout: "Goal, rules i next steps su osveženi iz zadatka.",
                      stderr: "",
                    },
                  });
                } catch (seedError) {
                  setResult({
                    status: "error",
                    action: "seed-project-memory",
                    summary: "Project Memory nije uspeo da se poseje iz task teksta.",
                    details: {
                      returncode: 1,
                      stdout: "",
                      stderr: seedError instanceof Error ? seedError.message : "Nepoznata greška.",
                    },
                  });
                } finally {
                  setIsSeeding(false);
                }
              }}
            >
              {isSeeding ? "Sejem..." : "Posej iz task teksta"}
            </button>
          </div>
        </div>
        <p className="helper-text">
          Ovo je najbrži način da sistem prepozna glavni cilj, važna pravila i prvi sledeći korak iz prirodnog opisa zadatka.
        </p>
        <div className="form-grid project-memory-seed-grid">
          <label className="settings-field">
            <span className="settings-field-label">Glavni cilj</span>
            <input
              type="text"
              value={seedGoal}
              placeholder="Napraviti playable HTML igru"
              onChange={(event) => setSeedGoal(event.target.value)}
            />
          </label>
          <label className="settings-field project-memory-seed-prompt">
            <span className="settings-field-label">Task tekst</span>
            <textarea
              value={seedTaskPrompt}
              placeholder="Mora imati score i restart. Prvo dovrši collision i game over flow."
              onChange={(event) => setSeedTaskPrompt(event.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="status-card wide-card runtimepilot-section-shell project-memory-overview-card">
        <div className="section-header page-flow-header">
          <div className="runtimepilot-section-heading">
            <span className="runtimepilot-section-glyph">
              <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="control" />
            </span>
            <div>
              <span className="status-label">Sačuvano stanje</span>
              <strong className="status-value">Šta agent trenutno treba da pamti</strong>
            </div>
          </div>
        </div>
        <div className="summary-metrics">
          <span>Status: {memory?.status === "active" ? "Aktivno" : "Prazno"}</span>
          <span>Ažurirano: {lastUpdatedLabel}</span>
          <span>Ažurirao: {memory?.updatedBy || "sistem"}</span>
          <span>Pravila: {counts?.rules ?? 0}</span>
          <span>Napredak: {counts?.progress ?? 0}</span>
          <span>Sledeće: {counts?.nextSteps ?? 0}</span>
        </div>
      </section>

      <section className="status-card wide-card runtimepilot-section-shell project-memory-editor-card">
        <div className="section-header page-flow-header">
          <div className="runtimepilot-section-heading">
            <span className="runtimepilot-section-glyph">
              <RuntimePilotIcon className="runtimepilot-section-glyph-icon" name="memory" />
            </span>
            <div>
              <span className="status-label">Glavni fokus</span>
              <strong className="status-value">Cilj projekta</strong>
            </div>
          </div>
        </div>
        <p className="helper-text">
          Ovo je jedna kratka rečenica koju agent ne sme da izgubi iz vida dok radi.
        </p>
        <div className="form-grid">
          <label className="settings-field">
            <span className="settings-field-label">Glavni cilj</span>
            <input
              type="text"
              value={draft.goal.text}
              placeholder="Napiši jednu kratku i jasnu ciljnu rečenicu."
              onChange={(event) => {
                setDraft({ ...draft, goal: { ...draft.goal, text: event.target.value } });
                setIsDirty(true);
              }}
            />
          </label>
          <label className="project-memory-lock-toggle">
            <input
              type="checkbox"
              checked={draft.goal.locked}
              onChange={(event) => {
                setDraft({ ...draft, goal: { ...draft.goal, locked: event.target.checked } });
                setIsDirty(true);
              }}
            />
            <span>Zaključaj cilj da ga agent ne menja olako</span>
          </label>
        </div>
      </section>

      <div className="project-memory-grid">
        <MemoryListEditor
          title="Važna pravila"
          summary="Ovde stavljaj stvari koje moraju da ostanu tačne i kada se kontekst razvlači."
          items={draft.rules}
          emptyText="Dodaj pravilo, na primer: jedan HTML fajl, score, restart, bez framework-a."
          allowLock
          onChange={(rules) => {
            setDraft({ ...draft, rules });
            setIsDirty(true);
          }}
        />
        <MemoryListEditor
          title="Već odlučeno"
          summary="Bitne tehničke odluke koje ne želiš da agent stalno preispituje."
          items={draft.decisions}
          emptyText="Dodaj odluku, na primer: koristimo canvas ili jedan output fajl."
          onChange={(decisions) => {
            setDraft({ ...draft, decisions });
            setIsDirty(true);
          }}
        />
        <MemoryListEditor
          title="Napredak"
          summary="Kratko šta je već završeno, da ne gubite vreme na ponavljanje."
          items={draft.progress}
          emptyText="Dodaj završenu stavku, na primer: postavljena game loop logika."
          onChange={(progress) => {
            setDraft({ ...draft, progress });
            setIsDirty(true);
          }}
        />
        <MemoryListEditor
          title="Sledeće"
          summary="Jedan ili nekoliko narednih koraka koje agent treba da gura prvo."
          items={draft.nextSteps}
          emptyText="Dodaj sledeći korak, na primer: dovršiti collision i game over flow."
          onChange={(nextSteps) => {
            setDraft({ ...draft, nextSteps });
            setIsDirty(true);
          }}
        />
      </div>

      <section className="status-card wide-card runtimepilot-section-shell project-memory-actions-card">
        <div className="inline-actions compact-actions">
          <button
            type="button"
            className="action-button"
            disabled={isSaving}
            onClick={async () => {
              setIsSaving(true);
              try {
                const saved = await saveProjectMemory(draft);
                onMemoryChange(saved.memory);
                setDraft(cloneMemoryToDraft(saved.memory));
                setIsDirty(false);
                setResult(saved);
              } catch (saveError) {
                setResult({
                  status: "error",
                  action: "save-project-memory",
                  summary: "Project Memory nije sačuvan.",
                  details: {
                    returncode: 1,
                    stdout: "",
                    stderr: saveError instanceof Error ? saveError.message : "Nepoznata greška.",
                  },
                });
              } finally {
                setIsSaving(false);
              }
            }}
          >
            {isSaving ? "Čuvam..." : "Sačuvaj Project Memory"}
          </button>
          <button
            type="button"
            onClick={() => {
              if (!memory) {
                return;
              }
              setDraft(cloneMemoryToDraft(memory));
              setSeedGoal(memory.goal.text);
              setIsDirty(false);
            }}
          >
            Vrati sačuvano stanje
          </button>
        </div>
      </section>

      <ActionResultPanel result={result} />
    </>
  );
}
