#!/usr/bin/env python3
"""TRULY surgical docx editor for the Faceless Blight (FBE) Current Tasks doc.

Same design as hb-doc-edit.py: edits word/document.xml IN PLACE inside the zip,
copies every other entry (fonts, styles, images) byte-for-byte, and changes the
text of EXACTLY ONE paragraph. It does NOT use pandoc or python-docx to write
(both destroy these font-embedding files). It can never delete, truncate, add,
or mass-edit.

Commands (single fixed target doc):
  fbe-doc-edit.py read
      Print every paragraph with an index (read-only).
  fbe-doc-edit.py replace-text "unique search text" "new text"
      Replace the visible text of the ONE paragraph matching the search string.

There is deliberately NO remove, NO add, NO mass-edit.
"""
import sys, os, time, zipfile, shutil, re

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews/Faceless Blight Current Tasks.docx"
LOCKOUT_SECONDS = 300
BACKUP_DIR = os.path.expanduser("~/.cw-doc-backups")
OUR_WRITE_MARKER = os.path.join(BACKUP_DIR, ".last-fbe-ticker-write")
DOCXML = "word/document.xml"

PARA_RE = re.compile(r'<w:p(?:\s[^>]*)?>.*?</w:p>|<w:p\s*/>', re.DOTALL)
# The name must END at '>' or at whitespace-then-attributes. A bare <w:t[^>]*>
# also matches the border tag <w:top .../>, and rewriting that as if it were a
# text run wipes out the paragraph's border/spacing markup and leaves the file
# unopenable. Self-closing <w:t/> holds no text, so it is excluded too.
WT_RE = re.compile(r'(<w:t(?:\s[^>]*?)?>)(.*?)(</w:t>)', re.DOTALL)


def die(msg, code=1):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(code)


def check_lockout():
    try:
        mtime = os.path.getmtime(DOC)
    except OSError:
        return
    age = time.time() - mtime
    if age >= LOCKOUT_SECONDS:
        return
    try:
        with open(OUR_WRITE_MARKER) as f:
            our_last = float(f.read().strip())
        if abs(mtime - our_last) < 10:
            return
    except (OSError, ValueError):
        pass
    die(f"LOCKOUT: doc modified {int(age)}s ago (need {LOCKOUT_SECONDS}s). Aborting.", 2)


def mark_our_write():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(OUR_WRITE_MARKER, "w") as f:
        f.write(str(time.time()))


def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(DOC).replace(" ", "_")
    dst = os.path.join(BACKUP_DIR, f"{base}.{stamp}.bak")
    shutil.copy2(DOC, dst)
    same = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
         if f.startswith(base + ".") and f.endswith(".bak")],
        key=os.path.getmtime, reverse=True)
    for old in same[3:]:
        try:
            shutil.move(old, os.path.join(os.path.expanduser("~/.Trash"), os.path.basename(old)))
        except OSError:
            pass
    return dst


def read_entries():
    out = []
    with zipfile.ZipFile(DOC) as z:
        if z.testzip() is not None:
            die("zip integrity check failed on source doc.", 5)
        for info in z.infolist():
            out.append((info, z.read(info.filename)))
    return out


def para_text(p):
    return "".join(m.group(2) for m in WT_RE.finditer(p))


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def xml_is_wellformed(xml):
    """True if this document.xml parses. Uses only the standard library."""
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(xml)
        return True
    except ET.ParseError:
        return False


def cmd_read():
    entries = read_entries()
    xml = next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")
    for idx, p in enumerate(PARA_RE.findall(xml)):
        t = para_text(p).strip()
        if t:
            print(f"[{idx}] {t}")


def replace_text(search, new_text):
    if not new_text.strip():
        die("refusing to write empty text (would blank the paragraph).", 5)

    entries = read_entries()
    orig_xml = next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")
    paras = PARA_RE.findall(orig_xml)

    matches = [i for i, p in enumerate(paras) if search.lower() in para_text(p).lower()]
    if not matches:
        die(f"no paragraph contains: {search}", 1)
    if len(matches) > 1:
        die(f"search matched {len(matches)} paragraphs; must match exactly one. "
            f"Use a longer, unique search string.", 1)
    tgt = matches[0]
    old_para = paras[tgt]
    if not WT_RE.search(old_para):
        die("target paragraph has no editable text run.", 1)

    state = {"done": False}
    def sub(m):
        if state["done"]:
            return m.group(1) + m.group(3)
        state["done"] = True
        return m.group(1) + xml_escape(new_text) + m.group(3)
    new_para = WT_RE.sub(sub, old_para)

    if new_para == old_para:
        print("No change needed (text already matches).")
        return

    new_paras = list(paras)
    new_paras[tgt] = new_para

    diffs = [i for i in range(len(paras)) if paras[i] != new_paras[i]]
    if diffs != [tgt]:
        die(f"internal guard: expected exactly 1 changed paragraph, got {diffs}.", 6)
    if len(new_paras) != len(paras):
        die("internal guard: paragraph count changed.", 6)
    if orig_xml.count(old_para) != 1:
        die("target paragraph not uniquely locatable in XML; aborting.", 6)
    new_xml = orig_xml.replace(old_para, new_para, 1)
    for i, p in enumerate(paras):
        if i != tgt and p not in new_xml:
            die(f"internal guard: paragraph {i} vanished.", 6)
    if len(PARA_RE.findall(new_xml)) != len(paras):
        die("internal guard: reparsed paragraph count mismatch.", 6)

    # The result must be WELL-FORMED XML. Regex splicing can silently produce
    # markup Word refuses to open; never write a document.xml that won't parse.
    if not xml_is_wellformed(orig_xml):
        die("this document's markup is already damaged and does not parse. "
            "Refusing to edit it until it is repaired.", 7)
    if not xml_is_wellformed(new_xml):
        die("internal guard: the edit would produce markup that Word cannot "
            "open. Nothing was written.", 6)

    check_lockout()
    bkp = backup()
    check_lockout()

    tmp = DOC + ".tmp_surgical"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for info, data in entries:
                payload = new_xml.encode("utf-8") if info.filename == DOCXML else data
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, payload)

        with zipfile.ZipFile(tmp) as zc:
            if zc.testzip() is not None:
                die("written zip failed integrity check; not swapping in.", 6)
            if set(zc.namelist()) != {i.filename for i, _ in entries}:
                die("zip entry set changed; aborting.", 6)
            for info, data in entries:
                if info.filename == DOCXML:
                    continue
                if zc.read(info.filename) != data:
                    die(f"non-document entry changed: {info.filename}; aborting.", 6)

        if os.path.getsize(tmp) < os.path.getsize(DOC) * 0.90:
            die("output <90% of original size; aborting.", 6)

        # CRITICAL — do NOT os.replace(tmp, DOC): on Google Drive File Stream a
        # rename swaps in a NEW file object, so the doc gets a fresh Drive file
        # ID and ALL its sharing permissions are destroyed (the "wiped doc that
        # loses sharing" bug). Instead overwrite the EXISTING file in place
        # (truncate + rewrite the same path/inode), which keeps the Drive file
        # ID — and therefore the sharing — intact.
        with open(tmp, "rb") as src, open(DOC, "wb") as dst:
            shutil.copyfileobj(src, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    mark_our_write()
    print(f"Replaced paragraph [{tgt}]. Backup: {bkp}")
    print(f"  old: {para_text(old_para).strip()[:80]}")
    print(f"  new: {new_text.strip()[:80]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if not os.path.isfile(DOC):
        die(f"FBE doc not found: {DOC}", 4)
    cmd = sys.argv[1]
    if cmd == "read":
        cmd_read()
    elif cmd == "replace-text":
        if len(sys.argv) < 4:
            die("replace-text requires: replace-text \"search\" \"new text\"", 1)
        replace_text(sys.argv[2], sys.argv[3])
    else:
        die(f"unknown command: {cmd}. Only 'read' and 'replace-text' exist.", 1)
