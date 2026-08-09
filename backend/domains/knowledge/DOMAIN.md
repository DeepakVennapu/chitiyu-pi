# Knowledge Domain

## Overview

Stores Deepak's personal knowledge graph: named entities (people, projects, vendors, places, concepts) with associated facts, typed fields, relationships, and events. Facts are embedded via `sentence-transformers` and stored in a `sqlite-vec` virtual table for semantic search.

**Design rule:** only the orchestrator crosses domain lines. This file documents everything a future developer needs to maintain the knowledge domain without reading any other domain.

---

## Data Model

### Entities (`entities`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 |
| `name` | TEXT | Canonical display name |
| `type` | TEXT | CHECK: `person` \| `project` \| `vendor` \| `place` \| `concept` \| `generic` |
| `aliases` | TEXT | JSON array of alternate names, default `'[]'` |
| `created_at` | TEXT | Local time, auto-set |
| `updated_at` | TEXT | Local time, auto-set |

Lookup by name is case-insensitive (`COLLATE NOCASE`). `get_or_create_entity` will reuse an existing entity if the name matches (case-insensitive) before inserting.

### Facts (`facts`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 |
| `entity_id` | INTEGER FK | References `entities(id)` ON DELETE CASCADE |
| `content` | TEXT | Free-form fact statement (e.g. "is allergic to shellfish") |
| `created_at` | TEXT | Local time, auto-set |

### Fields (`fields`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 |
| `entity_id` | INTEGER FK | References `entities(id)` ON DELETE CASCADE |
| `key` | TEXT | Field name (e.g. "email", "birthday") |
| `value` | TEXT | Field value |
| `type` | TEXT | `text` (default), `date`, `url`, etc. |
| `updated_at` | TEXT | Auto-set; upserts on `(entity_id, key)` |

Unique constraint: `(entity_id, key)` — one value per field key per entity.

### Relationships (`relationships`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 |
| `from_entity_id` | INTEGER FK | Source entity |
| `label` | TEXT | Relationship label (e.g. "works_at", "married_to") |
| `to_entity_id` | INTEGER FK | Target entity |
| `created_at` | TEXT | Auto-set |

Directional: `from → label → to`. Both FKs cascade on entity delete.

### Events (`events`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | INTEGER | Default 1 |
| `entity_id` | INTEGER FK | The entity the event belongs to |
| `title` | TEXT | Event name (e.g. "Birthday", "Contract renewal") |
| `event_date` | TEXT | `YYYY-MM-DD` |
| `recurrence` | TEXT | `none` (default) \| `annual` |
| `notes` | TEXT | Optional notes |
| `created_at` | TEXT | Auto-set |

### Embeddings (`vec_facts` — virtual table)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS vec_facts USING vec0(
    fact_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
```

- Backed by `sqlite-vec` extension. Created at schema init; silently skipped if `sqlite-vec` is not loaded.
- `fact_id` is a FK to `facts.id` (not enforced by the virtual table itself).
- `embedding` is 384-dimensional float vector (matches `all-MiniLM-L6-v2` output).
- Stored as raw bytes: `embedding.tobytes()` on write, `tobytes()` on query.

---

## Semantic Search Interface

### `embed(text: str) → np.ndarray`
`orchestrator/embedder.py` — lazy-loads `SentenceTransformer("all-MiniLM-L6-v2")` on first call. Returns a 384-dim `float32` numpy array with `normalize_embeddings=True` (unit vectors). The model is a singleton; subsequent calls reuse it.

### `semantic_search(conn, embedding, user_id, top_n=5) → list[dict]`
`domains/knowledge/search.py` — queries `vec_facts` using `vec_distance_cosine`:

```sql
SELECT f.id, f.content, f.entity_id, e.name AS entity_name,
       f.created_at,
       vec_distance_cosine(v.embedding, ?) AS distance
FROM vec_facts v
JOIN facts f ON f.id = v.fact_id
JOIN entities e ON e.id = f.entity_id
WHERE f.user_id = ?
ORDER BY distance ASC LIMIT ?
```

Returns a list of dicts. `distance` is cosine distance (0 = identical, 2 = opposite). Lower = more relevant. Returns `[]` silently if `sqlite-vec` is unavailable.

### Embedding Dimensions

| Model | Dimensions | Normalization |
|-------|-----------|--------------|
| `all-MiniLM-L6-v2` | **384** | L2-normalized (unit vectors) |

The virtual table schema `FLOAT[384]` must match. Changing the embedding model requires rebuilding `vec_facts`.

---

## NL Fact Extraction

`add_fact(conn, user_id, text) → str`

Sends user's text to Haiku (`DISPATCH_MODEL`) with a structured extraction prompt:

```
Extract the subject entity and fact from this statement.
Reply with JSON only: {"entity": "<name>", "entity_type": "<...>", "fact": "<fact text>"}
```

Then:
1. `get_or_create_entity` — upsert entity (case-insensitive name match)
2. `insert_fact` — store the fact text
3. `embed(fact_text)` — generate 384-dim embedding
4. `store_embedding` — `INSERT OR REPLACE` into `vec_facts`

If Haiku returns unparseable JSON, returns an error string asking the user to rephrase.

---

## Key DB Functions

### `get_or_create_entity(conn, user_id, name, entity_type="generic") → int`
Case-insensitive lookup; inserts if not found. Returns entity `id`.

### `insert_fact(conn, user_id, entity_id, content) → int`
Inserts a fact row. Returns the new `id`.

### `store_embedding(conn, fact_id, embedding) → None`
`INSERT OR REPLACE` into `vec_facts`. Swallows exceptions (e.g. if `sqlite-vec` not available).

### `get_entity_full(conn, user_id, entity_id) → dict`
Returns the entity row plus a `facts` key containing all facts for that entity, ordered newest first.

### `delete_entity_by_name(conn, user_id, name) → bool`
Case-insensitive lookup → hard delete from `entities`. Cascades to `facts`, `fields`, `relationships`, `events`.

### `get_all_entities(conn, user_id) → list`
All entities for the user, ordered alphabetically by name.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/knowledge/facts` | Add a fact (NL text → Haiku extraction → embed + store) |
| `GET` | `/knowledge/search?q=&top_n=5` | Semantic search over all facts |
| `GET` | `/knowledge/entities` | List all entities (name + type only) |
| `GET` | `/knowledge/entity/{name}` | Full entity: metadata + all facts |
| `DELETE` | `/knowledge/facts/{fact_id}` | Delete a single fact |

---

## Response Shapes

### `GET /knowledge/entities`
```json
[
  {"id": 1, "user_id": 1, "name": "Bunny", "type": "person", "aliases": "[]",
   "created_at": "2026-08-01 10:00:00", "updated_at": "2026-08-01 10:00:00"},
  ...
]
```

### `GET /knowledge/entity/{name}`
```json
{
  "id": 1,
  "name": "Bunny",
  "type": "person",
  "aliases": "[]",
  "created_at": "2026-08-01 10:00:00",
  "updated_at": "2026-08-01 10:00:00",
  "facts": [
    {"id": 7, "user_id": 1, "entity_id": 1,
     "content": "contributes $2,250/month to household",
     "created_at": "2026-08-01 10:05:00"},
    ...
  ]
}
```

### `GET /knowledge/search?q=diet+goals`
```json
[
  {"id": 12, "content": "targeting 190 → 170 lbs on a 10-week cut",
   "entity_id": 2, "entity_name": "Deepak",
   "created_at": "2026-08-02 09:00:00", "distance": 0.18},
  ...
]
```
Results ordered by cosine distance ascending (most relevant first).

---

## Orchestrator Context Injection

`KnowledgeDomain.inject_context()` is called on every message routed to the knowledge domain. It:
1. Embeds the incoming user message with `embed(message)`.
2. Calls `semantic_search(conn, emb, user_id, top_n=3)`.
3. Prepends the top 3 matching facts to the LLM system prompt as "Relevant memory:".

This enables the AI to surface related knowledge unprompted — e.g. if the user says "what do you know about my diet?" the three most relevant facts about Deepak's health constraints appear in context.

### Insights Engine Integration

`orchestrator/insights.py` calls the knowledge domain directly (not via HTTP) for both insight generation and the evening retro:

```python
query = "goals constraints diet weight finance habits sleep caffeine"
emb = embed(query)
facts = semantic_search(conn, emb, user_id, top_n=8)
```

The top 8 relevant facts are injected into the `[KNOWLEDGE — RELEVANT FACTS]` section of the insight prompt. This is the primary mechanism for personalizing insights with long-lived facts about Deepak that don't live in other domain tables (goals, preferences, constraints).

`orchestrator/retro.py` runs the same pattern with `top_n=5` and injects facts into `[KNOWLEDGE]` in the nightly retro context.

---

## Known Issues / Gaps

- **`fields`, `relationships`, `events` have no API endpoints** — the tables are created in schema but no router endpoints exist yet. They can only be read/written via direct DB access or custom tools.
- **No entity update endpoint** — entity type and aliases cannot be changed via the API. `get_or_create_entity` always upserts on name, never updates an existing entity's `type`.
- **`vec_facts` orphan risk** — deleting a fact via `DELETE /knowledge/facts/{id}` removes the `facts` row (which cascades from entities), but `vec_facts` has no FK constraint — orphan embedding rows can accumulate. The cosine query JOINs back to `facts`, so orphans are invisible in search results but waste space.
- **sqlite-vec dependency** — if the `sqlite-vec` extension is not loaded at connection time, embedding storage and semantic search silently degrade to no-ops/empty results. The `store_embedding` function swallows exceptions; `semantic_search` returns `[]` on any exception.
- **Single embedding model** — `all-MiniLM-L6-v2` is hardcoded. Changing models requires re-embedding all facts and rebuilding `vec_facts`.
