# Tuning Lab Tri Slot Receiver Rack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prelomiti `Tuning Lab -> Tri slota` iz postojeceg uskog grid prikaza u odobreni `receiver rack` raspored bez gubitka ijedne postojece kontrole ili podatka.

**Architecture:** Frontend ostaje bez backend promena: postojeci `draft.slots`, `patchSlotSettings(...)` i API payload-i ostaju isti, a menja se samo render hijerarhija. `TuningLabPage.tsx` predaje slot podatke novom skupu fokusiranih UI podkomponenti koje crtaju tri zone po slotu: identitet, glavne vrednosti i precision rack.

**Tech Stack:** React 19, TypeScript, Vite, pytest, packaged `frontend_dist`.

---

## File Map

### Postojeci fajlovi koje plan namerno dodiruje

- `frontend/src/pages/TuningLabPage.tsx:2090-2203`
  - sadasnji `Tri slota` blok sa `tuning-lab-slot-grid`
  - treba da postane tanji page-level orchestrator, ne mesto gde zivi sav slot markup
- `frontend/src/styles.css:6332-6341`
  - sadasnje bazne klase za slot grid i slot card
- `frontend/src/styles.css:7254-7265`
  - mobile collapse pravila za `tuning-lab-slot-grid`
- `frontend/src/styles.css:7510-7513`
  - intermediate breakpoint pravila za `tuning-lab-slot-grid`
- `tests/test_control_center_frontend_dist.py:705-769`
  - sadasnji tuning-lab source/style assertions koji eksplicitno gledaju `TuningLabPage.tsx`

### Novi fajlovi koje treba dodati

- `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
  - spoljni siroki modul i tri slot trake
- `frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx`
  - leva zona: labela, naziv, pomocni copy, `Profil`, `Thinking`, `Source`, status indikatori
- `frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx`
  - srednja zona: display tretman za `Context`, `Output` i 1-2 sekundarne vrednosti
- `frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx`
  - desna zona: 3 grupe finih kontrola i svih 9 parametara
- `frontend/src/components/tuning-lab/tuningLabSlotControlGroups.ts`
  - metadata za 9 finih parametara, grupisanje i label text

### Fajlovi koji ce biti osvezeni tek posle build koraka

- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

## Task 1: Zakljucati test kontrakt i izvaditi slot rack shell

**Files:**
- Create: `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
- Modify: `frontend/src/pages/TuningLabPage.tsx:2090-2203`
- Modify: `tests/test_control_center_frontend_dist.py:705-769`

- [ ] **Step 1: Dodati failing frontend source test za novi receiver rack kontrakt**

Dodati helper u `tests/test_control_center_frontend_dist.py` koji cita:

- `frontend/src/pages/TuningLabPage.tsx`
- sve `frontend/src/components/tuning-lab/*.tsx`
- po potrebi `frontend/src/components/tuning-lab/*.ts`

Taj helper treba da omoguci da test nastavi da radi i kada se markup izvuce iz `TuningLabPage.tsx`.

Dodati failing assertions za:

- `TuningLabTriSlotReceiverRack`
- `tuning-lab-receiver-rack`
- `tuning-lab-slot-row`
- `Tri slota`

- [ ] **Step 2: Pokrenuti ciljani test i potvrditi da pada**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: FAIL jer novi receiver rack tekst / klase jos ne postoje.

- [ ] **Step 3: Napraviti novi shell komponentni ulaz**

U `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx` napraviti komponentu koja prima:

- `slots`
- `onPatchSlot`
- po potrebi `referenceSlots` ili `draftSnapshot`

ali za sada renderuje samo:

- spoljni modul
- naslov sekcije
- mapiranje slotova u tri siroke trake

Bez finalnog sadrzaja zona.

- [ ] **Step 4: Zameniti inline slot grid pozivom nove komponente**

U `frontend/src/pages/TuningLabPage.tsx` izbaciti direktni render `tuning-lab-slot-grid` bloka i zameniti ga sa jednim pozivom `TuningLabTriSlotReceiverRack`.

Bitno:

- `patchSlotSettings(...)` logika ostaje ista
- page i dalje drzi state
- nova komponenta ne uvodi novi izvor istine

- [ ] **Step 5: Ponovo pokrenuti tuning-lab frontend source test**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: PASS za novi shell kontrakt.

- [ ] **Step 6: Commit**

```bash
git add tests/test_control_center_frontend_dist.py frontend/src/pages/TuningLabPage.tsx frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx
git commit -m "refactor: extract tuning lab tri-slot receiver rack shell"
```

## Task 2: Napraviti levu i srednju zonu kao hi-fi komandne blokove

**Files:**
- Create: `frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx`
- Create: `frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodati failing assertions za identity + display jezik**

U source/style test dodati assertions za nove markere:

- `tuning-lab-slot-identity-panel`
- `tuning-lab-slot-square-control`
- `tuning-lab-slot-led-row`
- `tuning-lab-slot-display-panel`
- `tuning-lab-slot-display-box`
- `Profil`
- `Thinking`
- `Source`
- `Context`
- `Output`

- [ ] **Step 2: Pokrenuti ciljani test i potvrditi pad**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: FAIL jer novi paneli i klase jos nisu implementirani.

- [ ] **Step 3: Implementirati `TuningLabSlotIdentityPanel.tsx`**

Panel treba da prikazuje:

- labelu slota
- naziv / ulogu slota
- kratak helper text
- tri kockasta komandna bloka za:
  - `Profil`
  - `Thinking`
  - `Source`
- 1-2 status indikatora koji koriste postojece slot informacije

Napomena:

- ovde ne izmisljati novu backend semantiku
- koristiti postojece `slot.label`, `slot.source` i postojece inference summary helper-e gde imaju smisla

- [ ] **Step 4: Implementirati `TuningLabSlotDisplayPanel.tsx`**

Panel treba da prikazuje:

- `Context`
- `Output`
- 1-2 sekundarne vrednosti koje stanu u srednju zonu bez prenatrpavanja

Koristiti jaci `display` tretman, ali zadrzati standardne input kontrole kada je vrednost editabilna.

- [ ] **Step 5: Dodati CSS za kockaste blokove i display prozore**

U `frontend/src/styles.css` dodati nove klase za:

- spoljni rack modul
- slot traku
- identity panel
- kockaste komandne blokove
- LED red
- display panel
- display box

Pri tome obrisati ili degradirati oslanjanje na:

- `.tuning-lab-slot-grid`
- `.tuning-lab-slot-card`

za ovu sekciju, bez lomljenja drugih tuning-lab delova.

- [ ] **Step 6: Pokrenuti frontend source test i potvrditi prolaz**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: PASS sa novim klasama i tekstom.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add tuning lab slot identity and display panels"
```

## Task 3: Uvesti precision rack sa 3 grupe i svih 9 finih kontrola

**Files:**
- Create: `frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx`
- Create: `frontend/src/components/tuning-lab/tuningLabSlotControlGroups.ts`
- Modify: `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodati failing assertions za precision rack**

Dodati assertions za:

- `tuning-lab-slot-precision-rack`
- `tuning-lab-slot-precision-group`
- `Sampling`
- `Stability`
- `Bias`
- svih 9 labela parametara:
  - `Temperature`
  - `Top-k`
  - `Top-p`
  - `Min-p`
  - `Repeat`
  - `Last N`
  - `Presence`
  - `Frequency`
  - `Seed`

- [ ] **Step 2: Pokrenuti ciljani test i potvrditi pad**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: FAIL jer precision rack jos nije prisutan.

- [ ] **Step 3: Premestiti metadata za finih 9 parametara u zaseban fajl**

U `tuningLabSlotControlGroups.ts` definisati:

- redosled kontrola
- grupu za svaku kontrolu
- labelu
- `step` logiku za integer / decimal inpute

Time se izbacuje inline niz iz `TuningLabPage.tsx:2168-2197`.

- [ ] **Step 4: Implementirati `TuningLabSlotPrecisionRack.tsx`**

Komponenta treba da:

- crta tri grupisana bloka
- renderuje svih 9 kontrola
- prikazuje i labelu i trenutnu vrednost
- koristi postojeci `patchSlotSettings(...)` tok preko callback-a

Ne menjati naziv polja u payload-u. Menja se samo raspored i prezentacija.

- [ ] **Step 5: Dodati CSS za trim rack izgled**

Dodati stilove za:

- precision rack wrapper
- precision group
- trim control row
- label + value head
- horizontal rail / thumb tretman

Bitno:

- izgled treba da bude hi-fi / receiver, ne genericki form controls grid
- i dalje mora ostati citljiv sa 9 parametara

- [ ] **Step 6: Pokrenuti frontend source test i potvrditi prolaz**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: PASS sa novim precision rack markerima.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx frontend/src/components/tuning-lab/tuningLabSlotControlGroups.ts frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py frontend/src/pages/TuningLabPage.tsx
git commit -m "feat: add tuning lab precision rack controls"
```

## Task 4: Draft/applied/preporuceno stanja i responsivni prelomi

**Files:**
- Modify: `frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx`
- Modify: `frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx`
- Modify: `frontend/src/styles.css:7254-7265,7510-7513`
- Modify: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Dodati failing assertions za state i responsive klase**

Dodati assertions za marker klase / tekst kao sto su:

- `tuning-lab-slot-state-draft`
- `tuning-lab-slot-state-active`
- `tuning-lab-slot-state-recommended`
- `tuning-lab-receiver-rack`
- `tuning-lab-slot-zones`

Ako implementacija izabere drugaciji naziv klasa, zadrzati isti smisao: test mora da zakljuca da stanja i responsivna hijerarhija stvarno postoje.

- [ ] **Step 2: Pokrenuti ciljani test i potvrditi pad**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: FAIL jer state/responsive detalji jos nisu prisutni.

- [ ] **Step 3: Uvesti jasno vidljiva stanja po slotu i kontroli**

Implementirati minimalno:

- indikator za `draft changed`
- indikator za `aktivno / trenutno`
- indikator za `recommended`

Koristiti postojece slot podatke i lokalno poredjenje `draft` vrednosti sa referentnim slot snapshot-om iz summary payload-a.

- [ ] **Step 4: Zavrsiti responsive prelome za 3-zone layout**

Pravila:

- desktop: 3 zone u jednoj traci
- srednja sirina: slot ide u 2 reda, bez gubitka grupa
- mobilno: identitet -> glavne vrednosti -> precision rack

Zameniti stara breakpoint pravila koja direktno ciljaju `.tuning-lab-slot-grid` sa novim klasama receiver rack-a.

- [ ] **Step 5: Pokrenuti frontend source test i potvrditi prolaz**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k tuning_lab -q`  
Expected: PASS sa state i responsive kontraktom.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/tuning-lab/TuningLabTriSlotReceiverRack.tsx frontend/src/components/tuning-lab/TuningLabSlotIdentityPanel.tsx frontend/src/components/tuning-lab/TuningLabSlotDisplayPanel.tsx frontend/src/components/tuning-lab/TuningLabSlotPrecisionRack.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: add tuning lab receiver rack states and responsive layout"
```

## Task 5: Build, packaged dist sync i verifikacija

**Files:**
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/index.html`
- Modify: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/assets/*`

- [ ] **Step 1: Pokrenuti relevantne pytest testove pre build sync-a**

Run: `python -m pytest tests/test_control_center_frontend_dist.py tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py -q`  
Expected: PASS

- [ ] **Step 2: Pokrenuti frontend build**

Run: `npm run build`  
Workdir: `frontend`  
Expected: uspesan TypeScript + Vite build bez greske

- [ ] **Step 3: Osveziti packaged `frontend_dist`**

Run:

```powershell
Remove-Item 'src\local_ai_control_center_installer\control_center_backend\frontend_dist\assets\*' -Recurse -Force
Copy-Item 'frontend\dist\*' 'src\local_ai_control_center_installer\control_center_backend\frontend_dist' -Recurse -Force
```

Expected:

- novi asset hash fajlovi prisutni
- `index.html` osvezen

- [ ] **Step 4: Ponovo pokrenuti relevantne pytest testove**

Run: `python -m pytest tests/test_control_center_frontend_dist.py tests/test_control_center_tuning_lab.py tests/test_control_center_tuning_lab_routes.py -q`  
Expected: PASS

- [ ] **Step 5: Proveriti u browseru stvarni UX**

Rucno potvrditi:

- `Tri slota` je jedan siroki modul
- sva tri slota su siroke trake
- `Profil / Thinking / Source` deluju kao kockasti komandni blokovi
- `Context / Output` deluju kao display prozori
- svih 9 finih kontrola je vidljivo i grupisano
- nema horizontalnog skrola na tipicnoj desktop sirini
- mobilni / usi breakpoint ne raspada hijerarhiju

- [ ] **Step 6: Commit**

```bash
git add src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "build: refresh packaged frontend dist for tuning lab receiver rack"
```
