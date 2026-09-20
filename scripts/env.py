import re
import sys
from pathlib import Path

README = Path("README.md")
ENV_FILE = Path(".env")

if not README.exists() or not ENV_FILE.exists():
    sys.exit(0)

print("✂️ Copying environment variable names to README...")
var_names = []
for line in ENV_FILE.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        var_names.append(line.split("=", 1)[0].strip())
var_names.sort()

if not var_names:
    sys.exit(0)

block = "\n```env\n" + "".join(f"{v}=\n" for v in var_names) + "```\n"
content = README.read_text()
new_content = re.sub(
    r"(<!--ENV-START-->).*?(<!--ENV-END-->)",
    lambda m: m.group(1) + block + m.group(2),
    content,
    flags=re.DOTALL,
)
if new_content != content:
    README.write_text(new_content)
    print("  Environment variables updated ✓")
