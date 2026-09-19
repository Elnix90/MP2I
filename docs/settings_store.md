# Settings store

Fichier : `db/settings_store.py` · Schéma : `db/sql/settings_schema.sql`

DB : **`data/bot_state.db`** (gitignorée, création auto). Stocke l'état runtime du
bot en clé→valeur JSON, dans une table `settings`. DB **séparée** de
`colloscope.db` : celle-ci est supprimée/régénérée à chaque mise à jour du
planning, les settings ne doivent pas y mourir.

## API

```python
from db.settings_store import get_setting, set_setting

get_setting(key: str, default=None) -> object   # JSON décodé, `default` si
set_setting(key: str, value: object) -> None    # clé manquante/illisible
```

- Toute valeur JSON-serialisable (`dict`, `list`, `int`, `str`, `bool`…).
- Erreurs DB : jamais levées — log `warning` + retour du `default`.
- `PRAGMA busy_timeout = 5000` : sérialise les accès concurrents.

## Clés utilisées

| Clé | Valeur | Qui écrit |
| :-- | :----- | :-------- |
| `ai.allowed_channels` | `list[int]` — salons où le bot IA répond | `/ai-allow`, `/ai-deny` via `core/ai.py` |
| `commands.fingerprint` | `str` — hash des sources de `/cmds` | `bot.py` |
| `commands.updatedAt` | `int` — timestamp du dernier sync | `bot.py` |

## Règles

- **État par instance** : c'est la donnée *privée* de chaque bot/dév. Ne pas y
  stocker de données partagées (elles vont dans `colloscope.db`, qui suit le
  système de versioning).
- **Ne pas éditer à la main** — format JSON dans la colonne `value` :
  ```sql
  SELECT * FROM settings;
  ```
- Le SQL vit dans `db/sql/` (`settings_schema.sql`, `settings_get.sql`,
  `settings_upsert.sql`), chargé via `db/sql.load("name")`.