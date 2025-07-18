# Product Requirements Document

## 1. Background & Motivation

The LXT whitepaper *“The Path to AI Maturity 2025 – An Executive Survey”* synthesises extensive research on how organisations progress along Gartner’s five‑level AI maturity curve fileciteturn1file18. The marketing team wants to repurpose the report’s data‑dense charts into a steady stream of bite‑sized LinkedIn posts that:

* Highlight one key insight per visual
* Drive traffic back to the full report landing page
* Are produced automatically to reduce manual effort and turnaround time

## 2. Goals

|  #   | Goal                                                                                               | KPI                                            |
| ---- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
|  G1  | Automatically generate **two distinct LinkedIn posts** for every figure/chart in the PDF           | 100 % coverage of detected images              |
|  G2  | Store posts (copy, image URL, description, index, timestamp) in NocoDB for scheduling              | 100 % write success, verified via API response |
|  G3  | Provide a **test mode** that processes exactly one *new* image at a time to support content review | Toggleable via `--test` flag                   |
|  G4  | End‑to‑end runtime < 10 min for full whitepaper on a typical laptop (M‑series Mac)                 | ≥ 10 figures processed in ⩽ 10 min             |

## 3. Out of Scope

* Publishing/scheduling the posts on LinkedIn (handled by Sprout queue)
* Captioning non‑chart decorative images (e.g. hero photos)
* Generating X/Twitter threads or other social formats (future work)

## 4. Personas & User Stories

| Persona              | Need                                      | User story                                                                                             |
| -------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Content Marketer** | Fast generation of on‑brand LinkedIn copy | “As a marketer, I want to review AI‑drafted posts in NocoDB so I can schedule them without rewriting.” |
| **Data Analyst**     | Confidence in correctness                 | “As the analyst, I want each post to cite the exact chart page/index so fact‑checking is easy.”        |
| **Developer**        | Simple, reproducible tooling              | “As the dev, I want to install deps with `uv` and configure via `.env` so the script is portable.”     |

## 5. Functional Requirements

### 5.1 PDF → Markdown

* Use **markitdown** CLI to convert `whitepaper.pdf` to Markdown, preserving figure references.
* Save intermediate MD to `/tmp/{slug}.md` for downstream context.

### 5.2 Image Extraction & Tracking

* Detect embedded raster images > 300 px wide; assign sequential `image_index`.
* Persist processing state in a lightweight SQLite DB (`state.db`) keyed by PDF SHA‑256 + `image_index`.

### 5.3 Content Generation

| Step | Model                   | Prompt outline                                                                                                                                             |
| ---- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
|  1   | **GPT‑4o Vision**       | “Describe the insight shown in this chart. Return JSON with `title`, `key_metric`, `one_sentence_summary`.”                                                |
|  2   | **GPT‑4.1**             | “Write a LinkedIn post for senior tech execs using the supplied `summary` and short MD excerpt. Conclude with call‑to‑action to download the full report.” |
|  3   | **GPT‑4.1 (variation)** | Rewrite the post with a different hook (question, stat, or bold claim).                                                                                    |

### 5.4 Persistence to NocoDB

* Table schema mirrors the attached CSV with sample rows:

  * `post` (text)
  * `image` (attachment URL)
  * `date_posted` (nullable DATETIME)
  * `image_description` (text)
  * `image_index` (int)
* Use NocoDB REST API (`/api/v1/db/data/{project}/{table}`) with API key from `.env`.

### 5.5 Operating Modes

* **Test mode** (`--test N`)   ▶ Process exactly one unprocessed image, starting from the highest completed `image_index`.
* **Prod mode** (default)     ▶ Loop through all remaining images.

### 5.6 CLI & Execution

```shell
uv pip install -r requirements.lock  # reproducible env
python whitepaper2li.py --pdf whitepaper.pdf --nocodb-table linkedin --test
```

Optional: add `make run-test` and `make publish` targets; cron‑ready entry‑point.

## 6. Non‑Functional Requirements

* **Dependency management:** `uv` + lockfile for deterministic installs.
* **Config:** All secrets via `.env` (see `env_example`).  Fail fast if any key missing.
* **Logging:** Structured JSON to stdout. Verbose flag for debugging.
* **Error handling:** Retry OpenAI calls (exponential backoff). Skip and log images that error > 3 ×.
* **Rate limiting:** Respect OpenAI header `x-ratelimit‑remaining`.
* **Licensing:** Output posts under CC‑BY so marketing can edit.

## 7. Environment Variables

| Var                   | Purpose                          |
| --------------------- | -------------------------------- |
|  `OPENAI_API_KEY`     | GPT‑4.1 & GPT‑4o access          |
|  `OPENAI_MODEL_GPT4`  | e.g. `gpt-4o-2025-05-13`         |
|  `NC_API_KEY`         | NocoDB personal token            |
|  `NC_BASE_URL`        | eg. `https://nocodb.yourorg.com` |
|  `NC_PROJECT`         | NocoDB project slug              |
|  `LI_LANDING_URL`     | CTA link appended to every post  |

## 8. Data Model Extensions (future‑proof)

Optional additional columns:

* `post_variant` ENUM(1,2)
* `status` ENUM(draft, approved, scheduled, published)
* `linkedin_post_id`

## 9. Success Metrics

* 0 runtime errors in CI.
* 100 % of images result in two unique, non‑empty posts in NocoDB.
* ≤ 5 % manual edits required before scheduling (marketing feedback loop).

## 10. Assumptions

* All charts are rasterised images inside the PDF (no vector drawings).
* NocoDB table already exists and attachment column auto‑uploads binary data.
* OpenAI quota is sufficient for < 50 image + text generations per run.

## 11. Risks & Mitigations

|  Risk                      | Impact                    | Mitigation                                                                        |
| -------------------------- | ------------------------- | --------------------------------------------------------------------------------- |
| Model hallucination        | Incorrect stats in post   | Embed numeric values directly from chart via Vision response; review in test mode |
| Markitdown conversion loss | Missing context sentences | Fall back to extracting adjacent text with `pdfplumber` if MD lacks heading       |
| NocoDB downtime            | Posts not saved           | Write fallback CSV to `/tmp/posts_{date}.csv`                                     |

## 12. Milestones

1. **Week 0:**  Repo scaffold, `uv` lock, `.env_example`.
2. **Week 1:**  PDF → MD + image extraction; local CSV output.
3. **Week 2:**  GPT‑4o + GPT‑4.1 integration; NocoDB write.
4. **Week 3:**  CLI flags, logging, docs; user acceptance testing.
5. **Week 4:**  Tag v1.0 & deploy via GitHub Actions.

## 13. Open Questions

* How should we deduplicate similar charts reused across pages?
* Do we require translation/localisation for non‑English audiences?
* Should the CTA link be appended or embedded as UTM‑tagged hyperlink?

---

**Latest revision:** <!-- autofill on save -->
