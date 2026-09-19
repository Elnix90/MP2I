"""System prompt assembly for the AI layer.

Combines the base personality prompt (``config/prompts/system.md``) with
optional server context and tool-use instructions.
"""

from core.config import cfg

TOOL_INSTRUCTIONS = """OUTILS DISPONIBLES :
- `web_search` : recherche web. À utiliser AVANT de répondre à toute question de fait, personne, événement, actualité, produit, version, lieu ou info récente.
- `web_fetch` : lire le contenu d'une URL précise (en général après web_search).
- `safe_eval_math` : calculatrice sécurisée et conversions d'unités. Utilise-la pour tout calcul, même simple.
- `image_ocr` : extraire le texte d'une image (URL, chemin ou base64).

RÈGLES D'UTILISATION :
1. Quand l'utilisateur dit « cherche », « recherche », « google », « trouve sur internet », « va voir », ou demande une info d'actualité / factuelle / une personne / un lieu / une version → appelle `web_search` IMMÉDIATEMENT, sans répondre avant d'avoir le résultat.
2. Utilise le VRAI mécanisme d'appel d'outil (function calling). N'écris JAMAIS un faux appel dans ton texte du genre `search(...)`, `web_search(...)` ou `« Résultat du futur »` : exécute réellement l'outil.
3. Cite toujours tes sources (titre + URL) quand tu utilises web_search / web_fetch.
4. N'invente jamais un résultat, une citation ou un fait : si l'outil est indisponible, dis-le honnêtement."""


def build_system_prompt(
    server_context: str | None = None,
    *,
    include_tools: bool = True,
) -> str:
    """Build the full system prompt for a request.

    Parameters
    ----------
    server_context : str | None
        Optional formatted server context to embed.
    include_tools : bool
        Whether to append the tool-use instructions (default: True).

    Returns
    -------
    str
        Assembled system prompt.
    """
    parts = [cfg.AI_SYSTEM_PROMPT]
    if server_context:
        parts.append(server_context)
    if include_tools:
        parts.append(TOOL_INSTRUCTIONS)
    return "\n\n".join(parts)
