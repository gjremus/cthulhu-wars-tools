#!/usr/bin/env python3
import docx
BASE = ("/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/"
        "My Drive/Personal/Games/Cthulhu Wars/Library at Celaeno/")
DOC = BASE + "library build current tasks.docx"
MIRROR = BASE + ".last_seen_tasks.md"
d = docx.Document(DOC)
lines = []
for p in d.paragraphs:
    if p.style.name.startswith("Heading"):
        lines.append("## " + p.text)
    else:
        lines.append(p.text)
with open(MIRROR, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("mirror regenerated:", len(lines), "paragraphs")
