import re
import subprocess
import sys
from pathlib import Path

GITIGNORE = Path(".gitignore")
README = Path("README.md")

# Build exclusion pattern for `tree -I`
excludes = [".git"]
if GITIGNORE.exists():
    for line in GITIGNORE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("!"):
            excludes.append(line.removeprefix("./").rstrip("/"))
pattern = "|".join(excludes) or ".git"

if subprocess.run(["which", "tree"], capture_output=True, check=True).returncode != 0:
    print(
        "'tree' not installed. Install with: apt-get install tree / brew install tree",
    )
    sys.exit(0)

tree_output = subprocess.run(
    ["tree", "-a", "-I", pattern],
    capture_output=True,
    text=True,
    check=True,
).stdout

if not README.exists():
    sys.exit(0)

content = README.read_text()
block = f"\n```\n{tree_output}```\n"
new_content = re.sub(
    r"(<!-- TREE-START -->).*?(<!-- TREE-END -->)",
    lambda m: m.group(1) + block + m.group(2),
    content,
    flags=re.DOTALL,
)
if new_content != content:
    README.write_text(new_content)
