# Translation Alignment App — Brainstorm Notes

**Date:** 2026-04-22  
**Origin session:** Aramaic Root Atlas (aramaic-root-atlas project)  
**Status:** Early brainstorm — scope decomposition done, first clarifying question pending answer

---

## Inspiration

Professor Zhang Chen (UIC): https://staff.uic.edu.cn/zhanchen/en  
Example project: http://124.223.33.6/bible-mt5/  

A parallel alignment viewer comparing Slavonic 1751, Greek Byzantine, and two Chinese NT versions (1864 固里 and 1910 英诺肯提乙). Color-coded divergence:
- **Green underline** = minor deviation (synonymous, stylistic)
- **Red underline** = major variant (semantic change, addition/substitution)
- **No underline** = fully aligned

The idea: build something similar but (a) for a broader or different set of text traditions, (b) with root-level linguistic analysis (not just string diff), and (c) with a scholar review / gold standard workflow.

---

## Core Concept

A **machine-in-the-loop annotation system** for parallel biblical/ancient text alignment:

1. Machine proposes alignments and variant classifications automatically
2. Students and scholars verify, correct, or reject proposals
3. After X approvals from qualified reviewers → entry becomes **published gold standard**
4. Gold standard data is exportable for academic use (TEI XML, CSV, etc.)

---

## Scope Decomposition

Three independent subsystems — each its own spec → plan → implementation cycle:

### Sub-project 1: Parallel Alignment Viewer (MVP)
- Display 2–4 text traditions side by side for the same passage
- Color-coded variant highlighting (aligned / minor / major / added / omitted)
- Root-level diff engine (more rigorous than string diff — same root = aligned, cognate root = minor, different root = major)
- No auth required, read-only
- **Build this first**

### Sub-project 2: Machine Annotation Engine
- AI (Claude API) proposes alignments and classifies variants
- Stores proposals in a database with confidence scores
- Proposals displayed to reviewers as "pending"
- **Depends on Sub-project 1 viewer**

### Sub-project 3: Scholar Review Workflow
- User accounts with roles: student, scholar, editor
- Review queue: approve / reject / correct machine proposals
- Consensus threshold: X approvals → gold standard
- Gold standard publication + export (TEI XML, BibTeX, CSV)
- **Depends on Sub-project 2**

---

## Available Scaffolding (from Aramaic Root Atlas)

Repo: `/Users/jfresco16/Google Drive/Claude/aramaic-root-atlas`  
Production: https://aramaic-root-atlas.onrender.com

### Directly reusable:
- **`aramaic_core/`** Python package — corpus loading, root extraction, transliteration (Syriac ↔ Latin/Hebrew/Arabic), cognate lookup, morphological analysis
- **Flask + Jinja2 app pattern** — single `app.py`, `_init()` lazy loader, global state pattern
- **`static/style.css`** — full design system: CSS variables, dark mode, corpus-color palette, nav, modals, settings panel, responsive layout
- **`templates/base.html`** — nav, i18n proxy `t()`, 4-language switcher (EN/ES/HE/AR), RTL support, settings dropdown, bookmarks, QR share modal
- **`data/i18n.json`** — i18n pattern (EN/ES/HE/AR keys)
- **Corpus CSV format**: `book_order, book, chapter, verse, reference, text` — any tradition can be loaded this way

### Existing corpora (4):
| ID | Tradition | Verses |
|----|-----------|--------|
| `peshitta_nt` | Peshitta NT (Syriac) | 7,440 |
| `peshitta_ot` | Peshitta OT (Syriac) | 23,072 |
| `biblical_aramaic` | Biblical Aramaic (Hebrew square) | 269 |
| `targum_onkelos` | Targum Onkelos (Syriac) | 5,846 |

### Already loaded (via bible.helloao.org / SBLGNT):
- Greek NT (SBLGNT) — 7,939 verses
- English WEB, Spanish RV1909, Hebrew WLC, Arabic Van Dyck translations

### Root-level diff logic (already implemented in ARA):
- `_translit_to_dash(syriac)` → Latin root key (e.g. SH-L-M)
- `_root_translit(root, script)` → script-aware transliteration
- Sister roots (2/3 consonant overlap) already computed for "minor variant" detection

---

## Open Question (answer this at session start)

**What text traditions should this cover?**

- **a) Aramaic-focused** — same 4 ARA corpora + Greek NT + Hebrew OT as reference columns
- **b) Semitic broadly** — Aramaic, Hebrew, Arabic, Syriac, Ethiopic traditions
- **c) Biblical texts across all major traditions** — Greek, Latin, Slavonic, Syriac, Coptic, Armenian, Chinese, etc. (Prof. Chen scope)
- **d) Open-ended / user-defined** — scholars load any parallel text; app is a general platform

The answer determines: how many corpora to ship, whether the diff engine needs to be language-agnostic, and how complex the data ingestion pipeline needs to be.

---

## Key Design Tensions to Resolve

1. **Fixed corpus set vs. user-loadable corpora** — fixed is simpler but limits reach; user-loadable requires a corpus management UI and ingestion pipeline
2. **Root-level diff (Aramaic-specific) vs. token-level diff (language-agnostic)** — root diff is more scholarly for Semitic; token diff is the only option for Slavonic, Greek, Latin
3. **Auth complexity** — scholar accounts + consensus tracking requires a real database (PostgreSQL), not just CSVs
4. **Deployment** — Render (like ARA) is fine for the viewer; the annotation system with a live DB needs a different tier or service

---

## Suggested Session Start

1. Answer the "which traditions" question above
2. Pick Sub-project 1 (viewer) as the focus for the first spec
3. Run brainstorming → writing-plans → subagent-driven-development on that sub-project
4. Keep Sub-projects 2 and 3 parked until the viewer is live
