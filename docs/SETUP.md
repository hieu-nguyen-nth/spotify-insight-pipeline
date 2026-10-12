# Fresh setup and offline reproduction

Python 3.10+ is required. The measured environment used Python 3.12. No database, provider key or model runtime is needed to inspect the saved results or reproduce cost arithmetic and ranking. Download the evidence attachment into the repository root and extract it there, preserving `grading/`, `cost/` and `reports/`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m unittest discover -s tests
.venv/bin/python cost/calculator.py --out work/offline_calculator.json
./run.sh replay-ranking --records reports/completed_subset/records.json --out work/offline_ranking
```

Compare `membership.csv`, `ranking.csv` and `claims.csv` in work/offline_ranking against reports/completed_subset/. `scripts/verify_offline.py` runs those commands in a temporary clean copy with a fresh virtual environment, no credentials or persisted work database, and records actual outcomes. It additionally tests doubled dated rates and modified volume/limits without changing measured pilot usage/time. Dependency installation uses the package index; subsequent replay uses no network or model calls.

The full raw source is supplied by the course, not committed here. Download/unzip the eleven-file [course dataset](https://haas-ai-classes-fall-26.vercel.app/assignment5.html). The complete CSV must have 97,400,616 bytes and SHA-256 `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`. Development samples are in dataset/samples/. Full-source checking requires only the checker, saved grading export and original CSV:

```sh
python3 vendor/check_submission.py reference --full /path/to/spotify_reviews_18months.csv --analysis /path/to/spotify_reviews_18months.csv --out work/full_reference.json
python3 vendor/check_submission.py check --reference work/full_reference.json --submission grading --out work/full_check.json
```

The expected result is `review_required`, not a full-source pass: 416,027 missing classifications and unavailable input/output tokens on one documented failed request. Independent completed-subset integrity is reported separately.

## Explicit new inference in a fresh checkout

These are future commands, not additional claimed executions. They must not be used to restart the stopped business run. Copy the blank .env.example to ignored .env and set TYPESAFE_API_KEY locally. The shared global spend ceiling is $4.80; additional-cap limits do not override it. Provider model allowlist is pinned Jev `jev-1.13.0`; no stronger fallback is configured.

```sh
./run.sh ingest --input /path/to/input.csv --db work/new_input.sqlite --out work/new_ingestion.json
./run.sh lean-pilot --db work/new_input.sqlite --out reports/new_input --scope new_input --batch-size 50 --prompt-version v3 --additional-cap-usd .01
# Inspect the prepared plan, then deliberately authorize model execution:
./run.sh lean-pilot --db work/new_input.sqlite --out reports/new_input --scope new_input --batch-size 50 --prompt-version v3 --additional-cap-usd .01 --execute-paid
# Only after complete enrichment and the local runtime setup below:
./run.sh analyze-pilot --db work/new_input.sqlite --out reports/new_input --output-token-cap 1024 --execute-paid
```

CSV columns are review_id, review_text, review_rating, review_likes, app_version and review_timestamp. Source rating is not an inference answer. Human labels must not be added to payloads. Arbitrary CSVs use this same schema; handle empty texts in ingestion. A small cap can intentionally stop work before completion; rerunning the same scope resumes committed state rather than relabeling completed IDs. Never retry an unknown paid outcome without its documented reconciliation/authorization.

## Pinned local generation runtime

Actual generation used [Ollama 0.40.3](https://github.com/ollama/ollama/releases/tag/v0.40.3), its bundled CPU llama-server and `qwen2.5:3b-instruct-q4_K_M`. The model registry digest was `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`; the GGUF blob digest was `5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6`. Runtime binaries/model weights are external downloads, not submission assets. The following reproduces the recorded macOS runtime layout; select the equivalent release for a different platform and record the change rather than claiming identical hardware/timing.

```sh
mkdir -p work/runtime/ollama work/models
curl -fL https://github.com/ollama/ollama/releases/download/v0.40.3/ollama-darwin.tgz -o work/runtime/ollama-darwin.tgz
tar -xzf work/runtime/ollama-darwin.tgz -C work/runtime/ollama
# Run in one terminal and keep it running:
OLLAMA_NO_CLOUD=true OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/work/models" work/runtime/ollama/ollama serve
# In another terminal, download the local weights (no inference API charge):
OLLAMA_HOST=127.0.0.1:11434 work/runtime/ollama/ollama pull qwen2.5:3b-instruct-q4_K_M
# Check the registry digest before generation:
curl -f http://127.0.0.1:11434/api/tags
# Keep the matching CPU completion server running in a third terminal:
work/runtime/ollama/llama-server --model work/models/blobs/sha256-5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6 --alias qwen2.5:3b-instruct-q4_K_M --host 127.0.0.1 --port 11435 --ctx-size 8192 --parallel 1 --n-gpu-layers 0
```

The implementation reads the registry on port 11434 and sends bounded JSON generation to port 11435, with temperature zero, seed seven, a non-thinking model and an editable 32–4096 output-token cap (measured cap 1024). It stops on an incomplete/invalid local response and preserves it; no paid fallback is configured. Hardware/electricity are unmeasured. Environment/model location settings are documented in the [Ollama FAQ](https://docs.ollama.com/faq).

Database/deployment replication is optional for grading replay. See database/README.md for the actual Free schema and explicit upload, and backend/ for the read-only deployed app. Keep database admin credentials local; only the publishable key belongs in the backend environment.
