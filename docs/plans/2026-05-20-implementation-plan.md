# Implementation Plan

Date: 2026-05-20

## Goal

Build a stable `Local AI Control Center` product from a clean repo, using:

- stable installer/runtime core first
- portal and shell behavior second

## Phase 1: Windows Stable Core

### Task 1. Installer contract

- Build a text installer with numbered choices.
- Collect all choices before final download/install phase.
- Ask for:
  - install root
  - starter model
  - whether OpenCode should be installed
  - whether TurboQuant should be attempted
  - additional model read locations

### Task 2. Dependency bootstrap

- Verify and install:
  - git
  - Python
  - Node/npm
  - required build tools
- Distinguish:
  - hard fail
  - warning
  - optional skip

### Task 3. Runtime bootstrap

- Download or verify `llama.cpp`
- Download or verify selected model
- Install or verify `OpenCode`
- Attempt `TurboQuant` only if selected

### Task 4. Final download phase UX

- One-by-one file download queue
- Show:
  - current file
  - file index
  - total file count
  - remaining count
  - ETA

### Task 5. State and logs

- Write:
  - human-readable install log
  - JSON install report
- Include:
  - successful checks
  - successful installs
  - failures
  - failing step

### Task 6. Verification gate

- Installation is successful only if:
  - app installed
  - `llama.cpp` works
  - selected model present
  - active model configured
  - `OpenCode` works
  - first-run test passes

## Phase 2: Portal and model lifecycle

### Task 7. Server control

- Start/stop/open web for `llama.cpp`
- Accurate runtime status

### Task 8. Model lifecycle

- Detect manually added models
- Track downloaded/local/active states
- Allow active model switch
- Propagate active model to `OpenCode`

### Task 9. Browser/download flow

- Internet refresh
- size visibility
- real downloads
- direct source links
- visible progress

### Task 10. Update flow

- Check latest GitHub release
- Download new setup
- show progress
- launch installer

## Phase 3: Linux parity

### Task 11. Ubuntu x86_64

- Port the same installer contract
- Confirm runtime/OpenCode/model flow

### Task 12. Ubuntu arm64

- Same contract
- `TurboQuant` explicitly unsupported

## Verification Rule

No release without:

- installer run
- runtime run
- model ready
- OpenCode run
- accurate portal state


