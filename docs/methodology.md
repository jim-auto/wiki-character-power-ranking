# Methodology

`wiki-character-power-index` evaluates fictional character strength using Wikipedia text only.

The project is not a canon database, fan wiki, battle-board system, or original-work analysis tool. It is a text-grounded ranking pipeline.

## Pipeline

1. `data/seed_characters.yaml` stores the canonical character candidate list.
2. `src/sync_seed_characters.py` synchronizes the seed list into `data/characters.yaml`.
3. `src/fetch_wikipedia.py` fetches the Wikipedia page extract listed in `wikipedia_url`.
   It can use either MediaWiki Action API extracts or the official REST summary endpoint.
4. `src/extract_features.py` splits `description_raw` into sentences and keeps strength-related sentences.
5. Extracted sentences are classified into:
   - `abilities`: powers, equipment, training, skills, named techniques.
   - `feats`: explicit actions, battles, victories, saves, protection.
   - `statements`: descriptive strength claims or scale statements.
6. `src/scoring.py` applies deterministic text rules and records evidence.
7. `src/ranking.py` filters and renders power or text-evidence IQ rankings.
8. `src/battle.py` compares two characters using the already-computed evidence scores.
9. `src/export_site_data.py` exports `docs/data/characters.json` for GitHub Pages.

## Data Contract

Each character record follows this structure:

```yaml
name: string
wikipedia_url: string
media_type: manga | anime | movie | comic
universe: string
description_raw: text
extracted:
  abilities: list[string]
  feats: list[string]
  statements: list[string]
scores:
  attack: int
  defense: int
  speed: int
  abilities: int
  feats: int
  scale: int
score_evidence:
  attack: list[object]
  defense: list[object]
  speed: list[object]
  abilities: list[object]
  feats: list[object]
  scale: list[object]
total_score: int
tier: S | A | B | C
iq_score: int
iq_evidence: list[object]
```

`score_evidence` is an implementation extension that makes the score auditable. It is required for ranking output even though the minimal model can be represented without it.

`iq_score` is also an implementation extension. It means "Wikipedia text contains intelligence-related evidence" and does not mean real IQ.

## Wikipedia-Only Constraint

Allowed:

- Wikipedia article text fetched from the page in `wikipedia_url`.
- Wikipedia page title and revision metadata returned by the MediaWiki API or REST summary endpoint.
- Deterministic string rules stored in this repository.

Not allowed:

- Original manga, anime, film, or comic knowledge.
- Fan wiki information.
- Personal interpretation of a character's power.
- Inferred feats not written in the Wikipedia text.
- Cross-page enrichment unless that page is explicitly added to the record design in a future schema version.

## Initial Milestone

The sample data now starts from a 200-character seed list. The current public milestone is:

- 90 manga/anime characters
- 55 movie characters
- 55 Marvel/DC comic characters

The fetched text uses Wikipedia lead extracts by default for readability. For production runs, refresh `description_raw` with `src/fetch_wikipedia.py --intro-only`, then re-run extraction and scoring. If the Action API rate-limits a large refresh, use `src/fetch_wikipedia.py --source rest-summary --missing-only`.

## Future Extensions

The current structure is intentionally modular so these additions can be made without changing the scoring contract:

- API: expose ranking and filtering through a small HTTP service.
- Web UI: add search, filters, score breakdowns, and evidence views.
- Automatic updates: scheduled Wikipedia refresh with revision tracking.
- Multi-page records: support separate source pages for character profile, equipment, and media-specific variants.
- Rule audit tooling: report which rules most often affect rankings.
- Battle mode variants: compare by power, IQ evidence, or balanced score while preserving sentence evidence.
