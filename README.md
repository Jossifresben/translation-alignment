# Translation Alignment Viewer (MVP)

Focus-verse web viewer for parallel biblical texts. Pilot scope: Gospel of Mark in Greek NT (SBLGNT) + Peshitta (Syriac) + Clementine Vulgate, with word-level color-coded variant alignment pre-computed by Claude.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY for scripts
pytest                        # run tests
python app.py                 # run local viewer at http://localhost:5020
```

See `docs/superpowers/specs/` for the design spec and `docs/superpowers/plans/` for the implementation plan.
