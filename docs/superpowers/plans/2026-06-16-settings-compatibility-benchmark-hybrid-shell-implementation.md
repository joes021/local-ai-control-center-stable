# Settings + Compatibility + Benchmark Hybrid Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uskladiti `Settings`, `Compatibility` i `Benchmark` sa RuntimePilot hibridnim hi-fi shell-om tako da sve tri strane imaju isti spoljašnji jezik kao početna strana, ali zadrže jasan radni raspored prilagođen svom poslu.

**Architecture:** Zadržavamo postojeće zajedničke shell komponente (`PageFlowCard`, `RuntimePilotStatusDeck`, `RuntimePilotActionDeck`) i refaktorišemo samo raspored i zone unutar tri strane. Većina posla živi u tri page komponente i u centralnom `frontend/src/styles.css`, uz source i bundled regresione provere u `tests/test_control_center_frontend_dist.py`.

**Tech Stack:** React 19, TypeScript, Vite 7, centralni CSS u `frontend/src/styles.css`, pytest, packaged `frontend_dist`, PowerShell build/pakovanje.

---

## File Structure

- `frontend/src/pages/SettingsPage.tsx`
  - odgovoran za gornji shell, glavni action deck i tematske module `Settings` strane
- `frontend/src/pages/CompatibilityPage.tsx`
  - odgovoran za hibridni shell i podelu na kalkulator + truth panel
- `frontend/src/components/CompatibilityCalculatorPanel.tsx`
  - odgovoran za konkretan kalkulator, poruke primene i panel aktivnog stanja
- `frontend/src/pages/BenchmarkPage.tsx`
  - odgovoran za shell, akcije, graf, kontrole i kompaktniju istoriju run-ova
- `frontend/src/styles.css`
  - odgovoran za sve nove hybrid-shell layout klase i poravnanja
- `tests/test_control_center_frontend_dist.py`
  - odgovoran za source/bundle regresije koje proveravaju prisustvo novog shell jezika
- `src/local_ai_control_center_installer/control_center_backend/frontend_dist/*`
  - osveženi packaged frontend bundle posle Vite build-a

## Task 1: Dodati regresione testove za hybrid shell

**Files:**
- Modify: `tests/test_control_center_frontend_dist.py`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing test**

Dodati source-level test koji proverava da:

- `SettingsPage.tsx` sadrži `RuntimePilotStatusDeck` i `RuntimePilotActionDeck`
- `CompatibilityPage.tsx` sadrži `RuntimePilotStatusDeck` i `RuntimePilotActionDeck`
- `BenchmarkPage.tsx` sadrži `RuntimePilotStatusDeck` i `RuntimePilotActionDeck`
- `SettingsPage.tsx` promoviše tematske module umesto nasumične gomile kartica
- `CompatibilityPage.tsx` ima jasnu podelu na kalkulator i truth panel
- `BenchmarkPage.tsx` ima kompaktni prikaz aktivnosti i istorije

Primer jezgra testa:

```python
def test_settings_compatibility_benchmark_share_hybrid_shell_contract():
    settings_source = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    compatibility_source = Path("frontend/src/pages/CompatibilityPage.tsx").read_text(encoding="utf-8")
    benchmark_source = Path("frontend/src/pages/BenchmarkPage.tsx").read_text(encoding="utf-8")

    assert "RuntimePilotStatusDeck" in settings_source
    assert "RuntimePilotActionDeck" in settings_source
    assert "RuntimePilotStatusDeck" in compatibility_source
    assert "RuntimePilotActionDeck" in compatibility_source
    assert "RuntimePilotStatusDeck" in benchmark_source
    assert "RuntimePilotActionDeck" in benchmark_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k hybrid_shell_contract -q`
Expected: FAIL zato što nova struktura još nije do kraja implementirana ili test još ne odgovara source-u.

- [ ] **Step 3: Write minimal implementation**

Dodati samo onoliko test kodova koliko je potrebno da hvataju novi shell ugovor bez preteranog vezivanja za hash-ovane bundle nazive.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k hybrid_shell_contract -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_control_center_frontend_dist.py
git commit -m "test: cover hybrid shell contract"
```

## Task 2: Prepakovati Settings u komandni rack

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing test**

Dodati ili proširiti test da proverava prisustvo ovih novih zona u source-u:

- status deck za `aktivni profil`, `context`, `output`, `GPU`, `provider`
- glavni action deck sa akcijama `Sačuvaj bez primene`, `Primeni postojeće`, `Sačuvaj i primeni`, `Vrati podrazumevano`
- odvojene tematske zone za:
  - inference i sampling
  - context/output/GPU
  - OpenCode profil i bezbednost
  - pretragu i provider

Primer:

```python
assert "Sačuvaj bez primene" in settings_source
assert "Primeni postojeće" in settings_source
assert "Sačuvaj i primeni" in settings_source
assert "Vrati podrazumevano" in settings_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k settings_hybrid_shell -q`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

U `SettingsPage.tsx`:

- zadržati postojeće podatke i pomoćne funkcije
- presložiti JSX tako da vrh strane ide redom:
  - `PageFlowCard`
  - `RuntimePilotStatusDeck`
  - `RuntimePilotActionDeck`
  - veliki horizontalni moduli
- zadržati postojeće kontrole, ali ih grupisati po temama i skloniti duplu vizuelnu hijerarhiju
- rezultat posle primene vezati uz jasno označen panel aktivnog stanja

U `styles.css`:

- dodati klase tipa:
  - `.runtimepilot-settings-hybrid-grid`
  - `.runtimepilot-settings-module`
  - `.runtimepilot-settings-module-columns`
- poravnati module da koriste punu širinu i da ne prave uske vertikalne stubove

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k settings_hybrid_shell -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: reshape settings into hybrid command rack"
```

## Task 3: Prepakovati Compatibility u kalkulator + truth panel

**Files:**
- Modify: `frontend/src/pages/CompatibilityPage.tsx`
- Modify: `frontend/src/components/CompatibilityCalculatorPanel.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing test**

Dodati test koji proverava da source ima:

- top shell sa `PageFlowCard`, `RuntimePilotStatusDeck`, `RuntimePilotActionDeck`
- jasnu levu zonu za kalkulator
- jasnu desnu zonu za `Aktivno sada`, `Editor čeka proveru`, `Poslednja akcija`
- tekstualno odvajanje između predloga, editora i aktivnog runtime stanja

Primer:

```python
assert "Aktivno sada" in compatibility_source
assert "Editor čeka proveru" in compatibility_source
assert "Poslednja akcija" in compatibility_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k compatibility_hybrid_shell -q`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

U `CompatibilityPage.tsx`:

- zadržati postojeći data flow
- izgraditi vrh strane preko status i action deck-a
- radnu površinu podeliti u dve jasne zone:
  - široka leva zona za kalkulaciju
  - uža desna zona za stanje primene

U `CompatibilityCalculatorPanel.tsx`:

- result route panel i apply state panel učiniti vizuelno delom truth zone
- osigurati da korisnik odmah vidi razliku između:
  - izračunato
  - upisano u editor
  - stvarno aktivno

U `styles.css`:

- dodati klase tipa:
  - `.runtimepilot-compatibility-hybrid-layout`
  - `.runtimepilot-compatibility-main-zone`
  - `.runtimepilot-compatibility-truth-zone`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k compatibility_hybrid_shell -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CompatibilityPage.tsx frontend/src/components/CompatibilityCalculatorPanel.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: reshape compatibility into calculator and truth panel"
```

## Task 4: Prepakovati Benchmark u merni dek

**Files:**
- Modify: `frontend/src/pages/BenchmarkPage.tsx`
- Modify: `frontend/src/styles.css`
- Test: `tests/test_control_center_frontend_dist.py`

- [ ] **Step 1: Write the failing test**

Dodati test koji proverava da:

- Benchmark ima isti top shell obrazac
- graf ostaje centralni modul
- kontrole metrika/opsega žive uz graf
- aktivnost i istorija više nisu oslonjene na previsoku vertikalnu listu

Primer:

```python
assert "Pokreni izabrani test" in benchmark_source
assert "Pokreni celu bateriju" in benchmark_source
assert "Sačuvaj bateriju" in benchmark_source
assert "Vrati podrazumevano" in benchmark_source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k benchmark_hybrid_shell -q`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

U `BenchmarkPage.tsx`:

- presložiti vrh strane na `PageFlowCard` + `RuntimePilotStatusDeck` + `RuntimePilotActionDeck`
- kontrole benchmarka grupisati u jedan glavni kontrolni modul
- grafikon ostaviti centralno
- aktivne metrike i vremenski opseg držati neposredno uz graf
- istoriju i tekuće run-ove prebaciti u kompaktniji grid/tabelarni prikaz umesto previsoke kolone

U `styles.css`:

- dodati klase tipa:
  - `.runtimepilot-benchmark-hybrid-grid`
  - `.runtimepilot-benchmark-graph-shell`
  - `.runtimepilot-benchmark-history-grid`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_center_frontend_dist.py -k benchmark_hybrid_shell -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/BenchmarkPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py
git commit -m "feat: reshape benchmark into hybrid measurement deck"
```

## Task 5: Build, refresh packaged frontend and run regression verification

**Files:**
- Refresh: `src/local_ai_control_center_installer/control_center_backend/frontend_dist/**`
- Verify: `frontend/dist/**`
- Test: `tests/test_control_center_frontend_dist.py`
- Test: `tests/test_control_center_updates.py`
- Test: `tests/test_service_shell_regressions.py`
- Test: `tests/test_action_result_panel_layout.py`

- [ ] **Step 1: Run targeted UI regression tests**

Run:

```bash
python -m pytest tests/test_control_center_frontend_dist.py -q
```

Expected: PASS

- [ ] **Step 2: Build frontend**

Run:

```bash
frontend\\node_modules\\.bin\\tsc.cmd -b
frontend\\node_modules\\.bin\\vite.cmd build
```

Ako `node` nije u PATH-u, koristiti bundlovani runtime:

```bash
C:\\Users\\AzdahaI9\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\bin\\node.exe frontend\\node_modules\\typescript\\bin\\tsc -b
C:\\Users\\AzdahaI9\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\bin\\node.exe frontend\\node_modules\\vite\\bin\\vite.js build
```

Expected: successful TypeScript + Vite build

- [ ] **Step 3: Refresh packaged frontend**

Run:

```bash
if (Test-Path 'src\\local_ai_control_center_installer\\control_center_backend\\frontend_dist') {
  Get-ChildItem 'src\\local_ai_control_center_installer\\control_center_backend\\frontend_dist' -Force | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Force -Path 'src\\local_ai_control_center_installer\\control_center_backend\\frontend_dist' | Out-Null
Copy-Item 'frontend\\dist\\*' -Destination 'src\\local_ai_control_center_installer\\control_center_backend\\frontend_dist' -Recurse -Force
```

Expected: novi bundle prisutan u packaged `frontend_dist`

- [ ] **Step 4: Run wider verification**

Run:

```bash
python -m pytest tests/test_control_center_frontend_dist.py tests/test_control_center_updates.py tests/test_service_shell_regressions.py tests/test_action_result_panel_layout.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx frontend/src/pages/CompatibilityPage.tsx frontend/src/components/CompatibilityCalculatorPanel.tsx frontend/src/pages/BenchmarkPage.tsx frontend/src/styles.css tests/test_control_center_frontend_dist.py src/local_ai_control_center_installer/control_center_backend/frontend_dist
git commit -m "feat: implement hybrid shell across settings compatibility benchmark"
```
