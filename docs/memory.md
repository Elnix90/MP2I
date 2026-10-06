# Memory system

Fichier : `managers/memory.py` · Schéma : `db/sql/memory_schema.sql`

DB : **`data/memory.sqlite`** (gitignorée, création auto). Mémoire conversationnelle
du bot, persistée en SQLite avec recherche sémantique via **sqlite-vec** et
embeddings locaux **fastembed** (`utils/embedder`,
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions).

## Architecture

```mermaid
graph TB
    subgraph "get_context()"
        direction TB
        A[User message] --> B[utils/embedder]
        B --> C[vec0 HNSW search]
        C --> D[Top-K turns]
    end

    A --> E[user_facts table]
    E --> F[User facts]

    A --> G[session turns]
    G --> H[Last N turns]

    F --> I["Prompt assembly<br/>(budget ~4000 tokens)"]
    D --> I
    H --> I

    I --> J[LLM]
```

Quatre couches de mémoire, de plus en plus persistantes :

| Couche | Scope | Stockage | Contenu |
|--------|-------|----------|---------|
| **L1 Session** | channel/thread | SQLite (last N) | Derniers 15 échanges |
| **L2 User Facts** | user_id | SQLite `user_facts` | Faits extraits par le LLM cloud |
| **L3 Channel Facts** | channel_id | SQLite `channel_facts` | Résumé du canal |
| **L4 Full History** | tous | SQLite + vec0 | Tous les échanges, embeddings inclus |

## Schema SQL

### Diagramme ER

```mermaid
erDiagram
    memory_turns {
        TEXT turn_id PK
        INTEGER user_id
        TEXT user_name
        INTEGER guild_id
        INTEGER channel_id
        INTEGER thread_id
        TEXT user_content
        TEXT assistant_content
        TEXT scope_key
        REAL created_at
        REAL updated_at
    }

    vec_turns {
        float embedding
    }

    user_facts {
        TEXT fact_id PK
        INTEGER user_id
        TEXT fact
        TEXT source_turn_ids
        REAL created_at
        REAL updated_at
    }

    channel_facts {
        TEXT fact_id PK
        INTEGER channel_id
        TEXT fact
        TEXT source_turn_ids
        REAL created_at
        REAL updated_at
    }

    memory_turns ||--|| vec_turns : "rowid = rowid"
    memory_turns ||--o{ user_facts : "user_id"
    memory_turns ||--o{ channel_facts : "channel_id"
```

### `memory_turns`

```sql
CREATE TABLE memory_turns (
    turn_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    guild_id INTEGER,
    channel_id INTEGER,
    thread_id INTEGER,
    user_content TEXT NOT NULL,
    assistant_content TEXT,
    scope_key TEXT NOT NULL,     -- "channel:ID" ou "thread:ID"
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

`scope_key` est calculé par `make_scope_key()` :
- `channel:<id>` pour les salons normaux
- `thread:<id>` pour les threads

### `vec_turns` (virtual table sqlite-vec)

```sql
CREATE VIRTUAL TABLE vec_turns USING vec0(
    embedding float[384]
);
```

Index HNSW pour la recherche par distance L2 (les vecteurs sont
L2-normalisés, donc équivalent cosinus). Le `rowid` correspond
au `rowid` de la ligne `memory_turns` correspondante.

### `user_facts`

```sql
CREATE TABLE user_facts (
    fact_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    source_turn_ids TEXT,         -- JSON array de turn_ids
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

Faits persistants extraits automatiquement par le LLM cloud (1 petit appel
`chat.completions` par échange) lors de chaque échange.
Permettent au bot de se souvenir de l'utilisateur **entre les sessions**.

### `channel_facts`

```sql
CREATE TABLE channel_facts (
    fact_id TEXT PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    source_turn_ids TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
```

## API

```python
from managers.memory import MemoryManager, make_scope_key

memory = MemoryManager(max_history=15)

# --- CRUD ---
turn_id = memory.record_exchange(
    user_id=123,
    user_name="Alice",
    user_content="...",
    assistant_content="...",
    guild_id=1,
    channel_id=100,
)

turn = memory.get_turn(turn_id)  # exact ou prefix
turns = memory.list_turns(scope_key, limit=10)
memory.delete_turn(turn_id)
memory.clear_history(scope_key)  # supprime tout un scope

# --- Contexte pour le LLM ---
history = memory.get_history(scope_key, limit=15)  # legacy, last N
context = memory.get_context(  # intelligent
    scope_key,
    user_id=123,
    current_query="comment dériver ?",
)

# --- User facts ---
memory.add_user_fact(user_id, "Alice préfère les maths")
facts = memory.get_user_facts(user_id)
memory.clear_user_facts(user_id)

# --- Async wrappers (utilisés par bot.py) ---
await memory.record_and_sync(...)
await memory.delete_turn_and_sync(turn_id)
await memory.clear_history_and_sync(scope_key)
await memory.sync()
await memory.bootstrap()
```

## get_context() en détail

Sélectionne le contexte pertinent pour le LLM en 3 étapes :

1. **User facts** : récupère les faits persistants pour `user_id` (max 10)
   et les injecte comme message system
2. **Recherche sémantique** : `utils/embedder` → `vec0 MATCH`
   → top-5 turns les plus similaires (fallback keyword LIKE si < 3 résultats)
3. **Session turns** : les `max_history` derniers tours du scope, en excluant
   ceux déjà trouvés par les étapes 1-2

L'ordre d'injection dans le prompt :

```mermaid
graph TB
    subgraph Prompt
        direction TB
        A["🔧 system prompt<br/>(personnalité + contexte serveur)"]
        B["👤 system: user facts<br/>(ce qu'on sait de l'utilisateur)"]
        C["🔍 semantic hits<br/>(turns pertinents par embedding)"]
        D["💬 session turns<br/>(derniers échanges du scope)"]
        E["❓ user message courant"]
    end

    A --> B --> C --> D --> E
```

## Embeddings

```mermaid
sequenceDiagram
    participant U as User
    participant B as Bot
    participant M as MemoryManager
    participant E as utils/embedder (local)
    participant P as LLM API (Pollinations)
    participant DB as SQLite + vec0

    U->>B: message
    B->>M: record_and_sync()
    M->>DB: INSERT INTO memory_turns
    M->>E: embed(combined_text)
    E-->>M: float[384]
    M->>DB: INSERT INTO vec_turns (rowid, embedding)
    M->>P: extract_facts()
    P-->>M: ["fact1", "fact2"]
    M->>DB: INSERT INTO user_facts
```

- **Modèle** : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (ONNX, fastembed, chargé une fois au boot via `embedder.warmup()`)
- **Dimension** : 384 floats, L2-normalisés (vec0 classe en distance L2 ≈ cosinus)
- **Troncature** : 512 tokens — fastembed tronquerait à 128 sinon, `utils/embedder` remonte la limite explicitement
- **Stockage** : `struct.pack()` en BLOB dans `vec_turns`
- **Génération** : à chaque `record_and_sync()` en tâche de fond sur le texte combiné
  `"{user_name}: {user_content}\n{assistant_content}"`
- **Backfill** : `bootstrap()` génère les embeddings pour les turns existants
  qui n'en ont pas

Performance mesurée :
| Opération | Temps (500 vecteurs) |
|-----------|---------------------|
| Insertion | ~14ms |
| Recherche HNSW | ~2.9ms |
| Brute-force Python | ~83ms (28x plus lent) |

## Migration

Le schema gère automatiquement la migration depuis l'ancienne version (sans
`scope_key`) :

```mermaid
flowchart TD
    A[Connexion à memory.sqlite] --> B{PRAGMA table_info<br/>scope_key existe?}
    B -->|Oui| C[Rien à faire]
    B -->|Non| D[ALTER TABLE ADD COLUMN scope_key]
    D --> E[UPDATE FROM channel_id/thread_id]
    E --> C
    C --> F[CREATE TABLE IF NOT EXISTS ...]
    F --> G[Init vec_turns]
```

## Commandes Discord

| Commande | Description | Fichier |
|----------|-------------|---------|
| `/memory list [limit] [user]` | Affiche les échanges récents | `cmds/memory_list.py` |
| `/memory delete <turn_id>` | Supprime un échange | `cmds/memory_delete.py` |
| `/memory clear` | Efface tout le scope (admin) | `cmds/memory_clear.py` |

## Fichiers

| Fichier | Rôle |
|---------|------|
| `managers/memory.py` | MemoryManager, embeddings, recherche |
| `db/sql/memory_schema.sql` | Schema DDL |
| `db/sql/memory_*.sql` | Requêtes CRUD |
| `cmds/_memory.py` | Helper scope pour les commandes |
| `data/memory.sqlite` | DB (gitignorée) |

## Dépendances

| Package | Rôle |
|---------|------|
| `sqlite-vec` | Extension SQLite pour la recherche vectorielle HNSW |
| `fastembed` + `onnxruntime` | Embeddings 384-dim locaux (`utils/embedder`) + extraction de faits via API |
