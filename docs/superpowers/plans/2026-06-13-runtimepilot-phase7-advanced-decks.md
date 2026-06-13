# RuntimePilot Phase 7 Advanced Decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prosiriti RuntimePilot hi-fi jezik sa pocetne strane na `Napredno`, `Benchmark`, `Compatibility`, `Knowledge`, `OpenCode` advanced i `Tuning Lab`, tako da korisnik na svakom dubokom ekranu odmah vidi gde menja, gde primenjuje i gde cita rezultat.

**Architecture:** Uvesti mali shared sloj sekundarnih deck komponenti umesto novih jednokratnih layout hackova po svakoj strani. Postojeci data/loading kod u stranicama ostaje na mestu, a menja se shell, raspored kontrola, action rail i status/result prezentacija da svi duboki tokovi dele isti hi-fi receiver/deck jezik.

**Tech Stack:** React 19, TypeScript, Vite, CSS, packaged `frontend_dist`, pytest, lokalna browser verifikacija na `http://127.0.0.1:3210/`.

---

## File Map

**Create:**
- `frontend/src/components/SecondaryDeckShell.tsx`
- `frontend/src/components/DeckSection.tsx`
- `frontend/src/components/DeckActionRail.tsx`
- `frontend/src/components/DeckStatusStrip.tsx`
- `frontend/src/components/ResponsiveControlRow.tsx`
- `frontend/src/pages/AdvancedPage.tsx`

**Modify:**
- `frontend/src/App.tsx`
- `frontend/src/components/ActionResultPanel.tsx`
- `frontend/src/components/PageFlowCard.tsx`
- `frontend/src/pages/BenchmarkPage.tsx`
- `frontend/src/pages/CompatibilityPage.tsx`
- `frontend/src/pages/KnowledgePage.tsx`
- `frontend/src/pages/OpenCodePage.tsx`
- `frontend/src/pages/ObservabilityPage.tsx`
- `frontend/src/pages/TuningLabPage.tsx`
- `frontend/src/styles.css`
- `tests/test_control_center_frontend_dist.py`
- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

**Relevant existing verification targets:**
- `tests/test_control_center_benchmark.py`
- `tests/test_control_center_benchmark_routes.py`
- `tests/test_control_center_compatibility.py`
- `tests/test_control_center_knowledge.py`
- `tests/test_control_center_knowledge_routes.py`
- `tests/test_control_center_observability.py`
- `tests/test_control_center_opencode.py`
- `tests/test_control_center_tuning_lab.py`
- `tests/test_control_center_tuning_lab_routes.py`

### Task 1: Zakljucaj regresije za shared advanced deck jezik

**Files:**
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodaj failing assertions za shared deck shell markere**

Dodaj source/bundle assertions koje traze nove shared markere, na primer:

```python
assert "secondary-deck-shell" in source
assert "deck-action-rail" in source
assert "deck-status-strip" in source
assert "advanced-page" in source
assert "Prvo meri pa tek onda menjas" in bundled_js
```

- [ ] **Step 2: Pokreni samo ciljane frontend dist testove i potvrdi pad**

Run:

```bash
python -m pytest tests/test_control_center_frontend_dist.py -k "advanced or benchmark or tuning_lab or opencode or knowledge or compatibility" -q
```

Expected: FAIL zato sto novi shared markeri jos ne postoje u source-u i bundle-u.

- [ ] **Step 3: Commit test-only checkpoint**

```bash
git add tests/test_control_center_frontend_dist.py
git commit -m "test: lock advanced deck ui markers"
```

### Task 2: Uvedi shared secondary deck komponente i osnovni CSS sistem

**Files:**
- Create: `frontend/src/components/SecondaryDeckShell.tsx`
- Create: `frontend/src/components/DeckSection.tsx`
- Create: `frontend/src/components/DeckActionRail.tsx`
- Create: `frontend/src/components/DeckStatusStrip.tsx`
- Create: `frontend/src/components/ResponsiveControlRow.tsx`
- Modify: `frontend/src/components/ActionResultPanel.tsx`
- Modify: `frontend/src/components/PageFlowCard.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Napravi shared shell API bez page-specific logike**

Predlozena minimalna forma:

```tsx
export function SecondaryDeckShell({
  eyebrow,
  title,
  summary,
  statusStrip,
  actionRail,
  children,
}: SecondaryDeckShellProps) {
  return <section className="secondary-deck-shell">{children}</section>;
}
```

- [ ] **Step 2: Dodaj deck section, action rail i status strip primitive**

Svaka komponenta mora da ima sopstvenu klasnu granicu (`deck-section`, `deck-action-rail`, `deck-status-strip`) i da podrzi stacking na usim sirinama bez ruznog prelamanja.

- [ ] **Step 3: Uvedi shared CSS tok za hi-fi sekundarne ekrane**

Dodaj u `frontend/src/styles.css`:

```css
.secondary-deck-shell { /* shared frame */ }
.deck-section { /* hi-fi module faceplate */ }
.deck-action-rail { /* right command stack / top strip */ }
.deck-status-strip { /* compact live/status row */ }
.responsive-control-row { /* wraps buttons/selects cleanly */ }
```

- [ ] **Step 4: Uskladi ActionResultPanel i PageFlowCard sa novim shell-om**

Ne praviti novi rezultat komponentni haos ako vec postoji `ActionResultPanel`; samo ga uklopiti da vizuelno prati novi deck sistem.

- [ ] **Step 5: Pokreni TypeScript build**

Run:

```bash
npm run build
```

Workdir:

```text
frontend
```

Expected: uspesan `tsc -b && vite build`.

- [ ] **Step 6: Commit shared deck temelj**

```bash
git add frontend/src/components/SecondaryDeckShell.tsx frontend/src/components/DeckSection.tsx frontend/src/components/DeckActionRail.tsx frontend/src/components/DeckStatusStrip.tsx frontend/src/components/ResponsiveControlRow.tsx frontend/src/components/ActionResultPanel.tsx frontend/src/components/PageFlowCard.tsx frontend/src/styles.css
git commit -m "feat: add shared advanced deck shell"
```

### Task 3: Uvedi petotabni top flow i novi `Napredno` hub

**Files:**
- Create: `frontend/src/pages/AdvancedPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Dodaj `advanced` u page meta i primarnu navigaciju**

Primary flow treba da bude:

```ts
["home", "server", "models", "opencode", "advanced"]
```

Stare duboke stranice ostaju dostupne kroz `Napredno` hub i direktne akcione linkove.

- [ ] **Step 2: Napravi `AdvancedPage` kao sekundarni hi-fi hub**

Hub mora da ima:

- levi opisni modul
- srednji "glavni display" sta ovde dolazi i kojim redom se koristi
- desni action rail za `Benchmark`, `Tuning Lab`, `Compatibility`, `Knowledge`, `Observability`

- [ ] **Step 3: Odrzi stare `MORE_PAGE_SECTIONS`, ali ih spusti iza novog huba**

`Logs`, `Repair`, `Updates`, `Project Memory`, `Help`, `Jobs`, `Fleet` i `Workflows` ne smeju nestati; samo vise ne smeju biti prvi vizuelni kontakt za duboke tokove.

- [ ] **Step 4: Dodaj failing/passing source markers u testu ako jos fale**

Run:

```bash
python -m pytest tests/test_control_center_frontend_dist.py -k "advanced_page or runtimepilot" -q
```

Expected: PASS.

- [ ] **Step 5: Commit novi advanced hub**

```bash
git add frontend/src/App.tsx frontend/src/pages/AdvancedPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add advanced hi-fi hub"
```

### Task 4: Prepakuj `Benchmark` i `Observability` u merni deck jezik

**Files:**
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/pages/ObservabilityPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Benchmark shell prebaci na SecondaryDeckShell**

Gornji deo mora jasno da razdvoji:

- status/scope strip
- komande za pokretanje baterije ili selected run
- rezultat posle klika
- display deo za grafikon i istoriju

- [ ] **Step 2: Aktivna metrika i vremenski opseg stavi u jedan kompaktan display header**

Mora da podrzi multi-select za `Input tokeni`, `Output tokeni`, `Ukupno tokeni`, uz zaseban range strip (`1m`, `5m`, `15m`, `1h`) u istoj horizontalnoj zoni.

- [ ] **Step 3: Istoriju run-ova sabij u nize, preglednije kartice**

Zabranjen povratak na jednu previsoku vertikalnu kolonu.

- [ ] **Step 4: Observability prebaci u isti hi-fi telemetry deck**

Isti jezik kao Benchmark:

- status strip gore
- display i signal sredina
- akcije i sledeci koraci odvojeni

- [ ] **Step 5: Pokreni ciljane testove**

```bash
python -m pytest tests/test_control_center_benchmark.py tests/test_control_center_benchmark_routes.py tests/test_control_center_observability.py tests/test_control_center_frontend_dist.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit benchmark/observability deck**

```bash
git add frontend/src/pages/BenchmarkPage.tsx frontend/src/pages/ObservabilityPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: restyle benchmark and observability decks"
```

### Task 5: Prepakuj `Compatibility` i `Knowledge` u action-clarity deck

**Files:**
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/pages/KnowledgePage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Compatibility podeli na izbor, primenu i rezultat**

Potrebna tri jasno odvojena nivoa:

- izbor modela/scope-a
- context/VRAM/offload kontrole
- rezultat i aktivna vrednost koja je trenutno primenjena

- [ ] **Step 2: Aktivne brojcane vrednosti u Compatibility ucini eksplicitnim**

Kada korisnik klikne `Primeni`, mora odmah da vidi:

```text
Aktivna vrednost: 131072
Primenjeno na: runtime config
Rezultat gledaj u: ...
```

- [ ] **Step 3: Knowledge prebaci u cist document/search transport**

Obavezno:

- vise prostora izmedju teksta, inputa i dugmadi
- cist srpski tekst bez unicode smeca
- jasna zona za `documents-only`, `documents+web`, `web-only`

- [ ] **Step 4: Pokreni ciljane testove**

```bash
python -m pytest tests/test_control_center_compatibility.py tests/test_control_center_knowledge.py tests/test_control_center_knowledge_routes.py tests/test_control_center_frontend_dist.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit compatibility/knowledge deck**

```bash
git add frontend/src/pages/CompatibilityPage.tsx frontend/src/pages/KnowledgePage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: restyle compatibility and knowledge decks"
```

### Task 6: Prepakuj `OpenCode` advanced i `Tuning Lab` u pravi control/mixer dizajn

**Files:**
- Modify: `frontend/src/pages/OpenCodePage.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: OpenCode advanced raspodeli u tri ravna modula**

Gornji nivo mora jasno da razdvoji:

- session/runtime signal
- preset/security/autonomy controls
- rezultat i sekundarne akcije

Zabranjeno je razvlacenje dugmadi preko cele sirine bez jasne hijerarhije.

- [ ] **Step 2: Preset i security/autonomy kartice prepakuj u plocasti hi-fi raspored**

Posebno:

- `Ime preset-a` puno sirine
- akcije ispod inputa u jednoj horizontali kad ima mesta
- security dropdown-i u istoj horizontali
- `Sacuvaj OpenCode podesavanja` ispod, kao odvojen apply sloj

- [ ] **Step 3: Tuning Lab slotove pretvori u stvarne mikseta/deck module**

Svaki slot treba da ima:

- identitet/profil levo
- `Context` i `Output` u sredini
- 9 finih kontrola desno
- iste visine blokova po redu
- dropdown/popup slojeve koji izlaze iznad pozadine, ne ispod

- [ ] **Step 4: Napravi kombinovani picker za `Context` i `Output`**

Podrzati i preset izbor i slobodan unos:

```text
1k, 2k, 4k, 8k, 16k, 32k, 64k, 128k, 256k, 512k, 1M
```

plus manualan broj kada korisnik ne zeli preset.

- [ ] **Step 5: Pokreni ciljane testove**

```bash
python -m pytest tests/test_control_center_opencode.py tests/test_opencode_bootstrap.py tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py tests/test_control_center_frontend_dist.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit OpenCode/Tuning Lab deck**

```bash
git add frontend/src/pages/OpenCodePage.tsx frontend/src/pages/TuningLabPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: restyle opencode and tuning lab decks"
```

### Task 7: Responsive i action-clarity polish preko cele sekundarne zone

**Files:**
- Modify: `frontend/src/components/SecondaryDeckShell.tsx`
- Modify: `frontend/src/components/DeckActionRail.tsx`
- Modify: `frontend/src/components/DeckStatusStrip.tsx`
- Modify: `frontend/src/components/ResponsiveControlRow.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodaj breakpoints za laptop/tablet/mobile kompresiju**

Potrebno:

- da desni action rail prede u top strip kad nema sirine
- da status kartice ne prave uske stubove
- da najvaznije akcije ostanu vidljive bez "gde je dugme nestalo" momenata

- [ ] **Step 2: Dodaj jasne "posle klika gledaj ovde" i "otvara drugi ekran" cue-e**

Svaka duboka strana mora imati makar jedan jasan result/signal cue u istom modulu.

- [ ] **Step 3: Proveri scroll-to-top i sticky pomocne tokove**

Hi-fi polish ne sme da razbije vec uvedene pomocne UX mehanizme.

- [ ] **Step 4: Pokreni ciljane frontend dist testove**

```bash
python -m pytest tests/test_control_center_frontend_dist.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit responsive/action-clarity polish**

```bash
git add frontend/src/components/SecondaryDeckShell.tsx frontend/src/components/DeckActionRail.tsx frontend/src/components/DeckStatusStrip.tsx frontend/src/components/ResponsiveControlRow.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: polish responsive advanced deck behavior"
```

### Task 8: Rebuild, sync packaged bundle, full verify i browser smoke

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

- [ ] **Step 1: Napravi finalni frontend build**

Run:

```bash
npm run build
```

Workdir:

```text
frontend
```

Expected: Vite build uspe.

- [ ] **Step 2: Osvezi packaged `frontend_dist`**

Run:

```powershell
Copy-Item frontend\dist\* src\local_ai_control_center_installer\control_center_backend\frontend_dist -Recurse -Force
```

Expected: novi `index.html` i `assets/index-*` budu upisani u package bundle.

- [ ] **Step 3: Pokreni puni relevantni pytest skup**

```bash
python -m pytest tests/test_control_center_frontend_dist.py tests/test_control_center_benchmark.py tests/test_control_center_benchmark_routes.py tests/test_control_center_compatibility.py tests/test_control_center_knowledge.py tests/test_control_center_knowledge_routes.py tests/test_control_center_observability.py tests/test_control_center_opencode.py tests/test_opencode_bootstrap.py tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py -q
```

Expected: PASS.

- [ ] **Step 4: Uradi browser smoke na localhost-u**

Manuelno potvrditi:

- `Pocetna`
- `Runtime`
- `Modeli`
- `OpenCode`
- `Napredno`
- ulaz iz `Napredno` u `Benchmark`, `Tuning Lab`, `Compatibility`, `Knowledge`, `Observability`

Na svakoj strani potvrditi da je jasno:

- gde se menja
- gde se primenjuje
- gde se vidi rezultat

- [ ] **Step 5: Commit final packaged phase**

```bash
git add frontend/src/App.tsx frontend/src/components/SecondaryDeckShell.tsx frontend/src/components/DeckSection.tsx frontend/src/components/DeckActionRail.tsx frontend/src/components/DeckStatusStrip.tsx frontend/src/components/ResponsiveControlRow.tsx frontend/src/components/ActionResultPanel.tsx frontend/src/components/PageFlowCard.tsx frontend/src/pages/AdvancedPage.tsx frontend/src/pages/BenchmarkPage.tsx frontend/src/pages/CompatibilityPage.tsx frontend/src/pages/KnowledgePage.tsx frontend/src/pages/OpenCodePage.tsx frontend/src/pages/ObservabilityPage.tsx frontend/src/pages/TuningLabPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: ship phase7 advanced hi-fi decks"
```

## Review Notes

- Ovaj plan namerno ne menja backend ugovore osim ako tokom implementacije zatreba sitan status feedback dodatak.
- Ako tokom Task 3 postane jasno da petotabni top flow razbija previse postojece navigacije, fallback je da `Napredno` ostane glavni hub, a stare dodatne rute nastave da zive samo iza njega i kroz duboke CTA izlaze.
- Ako tokom Task 6 `Tuning Lab` postane previse gust, prioritet je da se prvo sacuva konzistentna hi-fi struktura, pa tek onda dodatno sabijanje detalja.
