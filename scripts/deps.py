import json
import re
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

README = Path("README.md")
REQUIREMENTS = Path("requirements.txt")

if not README.exists() or not REQUIREMENTS.exists():
    sys.exit(0)


def fetch_pypi(pkg):
    try:
        with urlopen(f"https://pypi.org/pypi/{pkg.lower()}/json", timeout=5) as r:
            info = json.loads(r.read())["info"]
            return info.get("summary", "").replace("\n", " ").strip(), info.get("version", "")
    except (URLError, KeyError):
        return "", ""


print("♻️ Updating dependencies list (fetching from PyPI)...")
lines = ["```markdown"]
for raw in REQUIREMENTS.read_text().splitlines():
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        continue
    pkg = re.split(r"[\[<>=!~\s]", raw)[0]
    summary, version = fetch_pypi(pkg)
    if summary:
        lines.append(f"- `{raw}` - {summary} (latest: {version})")
    elif version:
        lines.append(f"- `{raw}` - latest: {version}")
    else:
        lines.append(f"- `{raw}`")
lines.append("```")

block = "\n" + "\n".join(lines) + "\n"
content = README.read_text()
new_content = re.sub(
    r"(<!--DEPS-START-->).*?(<!--DEPS-END-->)",
    lambda m: m.group(1) + block + m.group(2),
    content,
    flags=re.DOTALL,
)
if new_content != content:
    README.write_text(new_content)
    print("  Dependencies updated ✓")
