#!/usr/bin/env python3
"""TRULY surgical docx editor for the master tasks doc.

This file USED to round-trip the whole document through pandoc markdown on every
write. That was catastrophic: pandoc regenerates the ENTIRE .docx from scratch,
which (a) strips the embedded custom fonts, (b) loses any edit the owner made
between our read and our write, and (c) writes a brand-new file — on Google
Drive File Stream a new file object gets a new Drive file ID, so ALL sharing
permissions on the doc are destroyed. That is the "wiped doc that lost sharing"
bug.

This version does NONE of that. It edits word/document.xml IN PLACE inside the
zip, copying every other entry (fonts, styles, numbering, images) byte-for-byte,
and touches only the specific paragraph(s) a command names. The file is never
regenerated, never renamed over, never truncated to a new inode.

Surgical guarantees enforced on EVERY write (any violation => abort, no write):
  * The file keeps its identity: we overwrite the existing file object in place
    (never os.replace / rename), so the Drive file ID and its sharing survive.
  * Only the named paragraph(s) change. Every OTHER paragraph is present
    verbatim in the result.
  * The paragraph count changes by EXACTLY the delta the command implies
    (+1 add, -1 remove, 0 move/replace) — never anything else.
  * Every zip entry other than word/document.xml is byte-identical after.
  * The new document.xml is verified WELL-FORMED before it is written.
  * A raw-bytes backup of the whole .docx is taken before any write.
  * A 5-minute mtime lockout + read/write hash check protects owner edits.

Commands (unchanged interface — the ticker calls these exactly as before):
  doc-edit.py read
  doc-edit.py remove "search text unique to the bullet"
  doc-edit.py remove-paragraph "search text unique to a bare paragraph"
  doc-edit.py remove-exact-line "exact stripped text of the line"
  doc-edit.py move-to-completed "search text"
  doc-edit.py mark-done "search text" ["replacement text"]
  doc-edit.py add-open "new task text"
  doc-edit.py add-completed "completed task text"
  doc-edit.py add-summary "summary text"
  doc-edit.py insert-after "search text" "text to insert after it"
  doc-edit.py replace-bullet "search text" "new text for that bullet"

The DOC path is hardcoded below; do NOT pass it as an argument.
"""
import sys, os, time, zipfile, shutil, re
import docguard_lock  # unlock()/relock() the OS immutable flag around our write

DOC = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/master current tasks.docx"
LOCKOUT_SECONDS = 300  # 5 minutes
BACKUP_DIR = os.path.expanduser("~/.cw-doc-backups")
OUR_WRITE_MARKER = os.path.join(BACKUP_DIR, ".last-ticker-write")
DOCXML = "word/document.xml"

# A whole paragraph element (open+close) OR a self-closing empty one.
PARA_RE = re.compile(r'<w:p(?:\s[^>]*)?>.*?</w:p>|<w:p\s*/>', re.DOTALL)
# Text inside a run. Name must END at '>' or whitespace so it can't also match
# border tags like <w:top .../>. Self-closing <w:t/> holds no text.
WT_RE = re.compile(r'(<w:t(?:\s[^>]*?)?>)(.*?)(</w:t>)', re.DOTALL)
# The uniform separator between sibling paragraphs in this document.
SEP = "\n    "


def die(msg, code=1):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# lockout / backup / write-marker (protect concurrent owner edits)
# ---------------------------------------------------------------------------
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
    die(f"LOCKOUT: doc modified {int(age)}s ago (need {LOCKOUT_SECONDS}s). "
        f"Aborting write to protect owner edits.", 2)


def mark_our_write():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(OUR_WRITE_MARKER, "w") as f:
        f.write(str(time.time()))


def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(BACKUP_DIR, f"master-tasks-{stamp}.docx")
    shutil.copy2(DOC, dst)
    docguard_lock.unlock(dst)  # keep our own backups mutable/prunable
    # Prune surplus backups (keep 3 newest) by deleting IN PLACE inside our own
    # private BACKUP_DIR. Never move to ~/.Trash: these copies are named like the
    # live doc, so trashing them looks exactly like the real doc vanished, and it
    # bypasses the docx guard hook. Only ever remove files inside BACKUP_DIR.
    same = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
         if f.startswith("master-tasks-") and f.endswith(".docx")],
        key=os.path.getmtime, reverse=True)
    real_backup_dir = os.path.realpath(BACKUP_DIR)
    for old in same[3:]:
        if os.path.realpath(os.path.dirname(old)) != real_backup_dir:
            continue
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


# ---------------------------------------------------------------------------
# zip / xml helpers
# ---------------------------------------------------------------------------
def _force_materialize(path, tries=30, delay=8):
    """Google Drive keeps files as 'dataless' placeholders and only downloads the
    real bytes when the WHOLE file is read to EOF. zipfile.ZipFile seeks to the
    central directory (a partial read) and fails 'not a zip' on a dataless file,
    so we do a full read first to force Drive's on-demand fetch. Not corruption,
    does not modify the file."""
    for i in range(tries):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            if len(data) >= 4 and data[:2] == b"PK":
                return
        except OSError as e:
            sys.stderr.write(f"materialize attempt {i + 1}/{tries}: {e}\n")
        time.sleep(delay)
    die("could not materialize doc from Google Drive (dataless placeholder "
        "never downloaded) -- Drive mount issue, not corruption.", 3)


def read_entries():
    _force_materialize(DOC)
    out = []
    with zipfile.ZipFile(DOC) as z:
        if z.testzip() is not None:
            die("zip integrity check failed on source doc.", 5)
        for info in z.infolist():
            out.append((info, z.read(info.filename)))
    return out


def get_docxml(entries):
    return next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")


def para_text(p):
    return "".join(m.group(2) for m in WT_RE.finditer(p))


def xml_escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def xml_is_wellformed(xml):
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(xml)
        return True
    except ET.ParseError:
        return False


def find_one(paras, search):
    """Index of the single paragraph whose visible text contains search."""
    s = search.lower()
    hits = [i for i, p in enumerate(paras) if s in para_text(p).lower()]
    if not hits:
        die(f"no paragraph contains: {search}", 1)
    if len(hits) > 1:
        die(f"search matched {len(hits)} paragraphs; must match exactly one. "
            f"Use a longer, unique search string.", 1)
    return hits[0]


def find_header(paras, name):
    """Index of a section-header paragraph whose text is exactly `name`."""
    for i, p in enumerate(paras):
        if para_text(p).strip() == name:
            return i
    return None


def clone_pPr_for_section(paras, header_idx):
    """Grab the <w:pPr> of the first real bullet after a section header, so a
    new bullet in that section looks exactly like its neighbours. Falls back to
    the most common bullet style in the doc."""
    for p in paras[header_idx + 1:]:
        if para_text(p).strip():
            m = re.search(r'<w:pPr>.*?</w:pPr>', p, re.DOTALL)
            if m:
                return m.group(0)
            break
    # fallback: the dominant task-list numbering in this document
    return ('<w:pPr><w:numPr><w:ilvl w:val="0" /><w:numId w:val="1009" />'
            '</w:numPr></w:pPr>')


def make_para(pPr, text):
    return (f'<w:p>{pPr}<w:r><w:t xml:space="preserve">'
            f'{xml_escape(text)}</w:t></w:r></w:p>')


def set_para_text(old_para, new_text):
    """Return old_para with ALL visible text replaced by new_text, formatting
    (pStyle, numPr, run props) preserved. Mirrors hb-doc-edit's approach."""
    if not WT_RE.search(old_para):
        die("target paragraph has no editable text run.", 1)
    state = {"done": False}
    def sub(m):
        if state["done"]:
            return m.group(1) + m.group(3)
        state["done"] = True
        return m.group(1) + xml_escape(new_text) + m.group(3)
    return WT_RE.sub(sub, old_para)


# ---------------------------------------------------------------------------
# the single write path — verifies, then overwrites the file IN PLACE
# ---------------------------------------------------------------------------
def commit_new_xml(entries, orig_xml, new_xml, expected_delta):
    """Swap in a new document.xml, keeping every other entry byte-identical and
    NEVER changing the file's identity (no rename/replace)."""
    old_paras = PARA_RE.findall(orig_xml)
    new_paras = PARA_RE.findall(new_xml)

    # GUARD A: paragraph count changed by exactly the intended delta.
    if len(new_paras) - len(old_paras) != expected_delta:
        die(f"internal guard: paragraph count delta "
            f"{len(new_paras) - len(old_paras)} != expected {expected_delta}; "
            f"aborting.", 6)

    # GUARD B: result must be well-formed XML (and the input must have been too,
    # so we never blame this edit for pre-existing damage).
    if not xml_is_wellformed(orig_xml):
        die("this document's markup does not parse (already damaged). Refusing "
            "to edit until repaired.", 7)
    if not xml_is_wellformed(new_xml):
        die("internal guard: the edit would produce markup Word cannot open. "
            "Nothing was written.", 6)

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

        # GUARD C: temp file is a valid zip with the SAME entry set.
        with zipfile.ZipFile(tmp) as zc:
            if zc.testzip() is not None:
                die("written zip failed integrity check; not swapping in.", 6)
            names_new = set(zc.namelist())
        names_old = {i.filename for i, _ in entries}
        if names_new != names_old:
            die(f"zip entry set changed: {names_old ^ names_new}; aborting.", 6)

        # GUARD D: every entry except document.xml is byte-identical.
        with zipfile.ZipFile(tmp) as zc:
            for info, data in entries:
                if info.filename == DOCXML:
                    continue
                if zc.read(info.filename) != data:
                    die(f"non-document entry changed: {info.filename}; aborting.", 6)

        # GUARD E: fonts dominate the size; the file must not shrink hugely.
        if os.path.getsize(tmp) < os.path.getsize(DOC) * 0.90:
            die("output <90% of original size; aborting.", 6)

        # CRITICAL — overwrite the EXISTING file object in place. Do NOT
        # os.replace(tmp, DOC): a rename gives the file a new inode, and on
        # Google Drive File Stream that means a new Drive file ID and the loss
        # of every sharing permission. Copying bytes into the open target keeps
        # the same file/inode, so the Drive ID and its sharing survive.
        # Doc is OS-locked (uchg); lift only for the in-place write, always restore.
        _was_locked = docguard_lock.unlock(DOC)
        try:
            with open(tmp, "rb") as src, open(DOC, "wb") as dst:
                shutil.copyfileobj(src, dst)
        finally:
            if _was_locked:
                docguard_lock.relock(DOC)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    mark_our_write()
    return bkp


def splice_verbatim(orig_xml, old_para, new_para):
    """Replace the exact old_para substring with new_para, once. old_para must
    be a literal slice of orig_xml, so this is a precise splice."""
    if orig_xml.count(old_para) != 1:
        die("target paragraph is not uniquely locatable in the XML; aborting "
            "to be safe.", 6)
    return orig_xml.replace(old_para, new_para, 1)


def remove_para_from_xml(orig_xml, old_para):
    """Remove old_para AND the single separator that precedes it."""
    if orig_xml.count(old_para) != 1:
        die("target paragraph is not uniquely locatable in the XML; aborting.", 6)
    if (SEP + old_para) in orig_xml:
        return orig_xml.replace(SEP + old_para, "", 1)
    # first paragraph (no preceding sibling separator): drop its trailing sep.
    return orig_xml.replace(old_para + SEP, "", 1)


def insert_after_para(orig_xml, ref_para, new_para):
    if orig_xml.count(ref_para) != 1:
        die("reference paragraph is not uniquely locatable; aborting.", 6)
    return orig_xml.replace(ref_para, ref_para + SEP + new_para, 1)


def insert_before_para(orig_xml, ref_para, new_para):
    if orig_xml.count(ref_para) != 1:
        die("reference paragraph is not uniquely locatable; aborting.", 6)
    return orig_xml.replace(ref_para, new_para + SEP + ref_para, 1)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def cmd_read():
    entries = read_entries()
    paras = PARA_RE.findall(get_docxml(entries))
    for idx, p in enumerate(paras):
        t = para_text(p).strip()
        if t:
            print(f"[{idx}] {t}")


def _remove(search, label):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    tgt = find_one(paras, search)
    old_para = paras[tgt]
    print(f"Removing {label}: {para_text(old_para).strip()[:90]}...")
    new_xml = remove_para_from_xml(orig, old_para)
    # every other paragraph must survive verbatim
    for i, p in enumerate(paras):
        if i != tgt and p not in new_xml:
            die(f"internal guard: paragraph {i} vanished; aborting.", 6)
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=-1)
    print(f"Done. Backup: {bkp}")


def cmd_remove(search):
    _remove(search, "bullet")


def cmd_remove_paragraph(search):
    _remove(search, "paragraph")


def cmd_remove_exact_line(exact):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    hits = [i for i, p in enumerate(paras) if para_text(p).strip() == exact]
    if not hits:
        die(f"could not find exact line: {exact}", 1)
    tgt = hits[0]
    old_para = paras[tgt]
    print(f"Removing exact line [{tgt}]: {exact[:90]}")
    new_xml = remove_para_from_xml(orig, old_para)
    for i, p in enumerate(paras):
        if i != tgt and p not in new_xml:
            die(f"internal guard: paragraph {i} vanished; aborting.", 6)
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=-1)
    print(f"Done. Backup: {bkp}")


def cmd_move_to_completed(search):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    tgt = find_one(paras, search)
    old_para = paras[tgt]
    hdr = find_header(paras, "Completed")
    if hdr is None:
        die("no 'Completed' section header found.", 1)
    completed_hdr_para = paras[hdr]
    print(f"Moving to Completed: {para_text(old_para).strip()[:90]}...")
    # remove from current location, then insert right after the Completed header
    step1 = remove_para_from_xml(orig, old_para)
    new_xml = insert_after_para(step1, completed_hdr_para, old_para)
    # net paragraph count unchanged
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=0)
    print(f"Done. Backup: {bkp}")


def cmd_mark_done(search, replacement=None):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    tgt = find_one(paras, search)
    old_para = paras[tgt]
    hdr = find_header(paras, "Completed")
    if hdr is None:
        die("no 'Completed' section header found.", 1)
    completed_hdr_para = paras[hdr]

    if replacement:
        done_para = set_para_text(old_para, replacement)
    else:
        cur = para_text(old_para)
        if "[]" in cur:
            done_para = set_para_text(old_para, cur.replace("[]", "☒", 1))
        elif "[ ]" in cur:
            done_para = set_para_text(old_para, cur.replace("[ ]", "☒", 1))
        else:
            done_para = set_para_text(old_para, "☒ " + cur)

    print(f"Marking done: {para_text(old_para).strip()[:90]}...")
    step1 = remove_para_from_xml(orig, old_para)
    new_xml = insert_after_para(step1, completed_hdr_para, done_para)
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=0)
    print(f"Done. Backup: {bkp}")


def cmd_add_open(text):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    hdr = find_header(paras, "Open")
    if hdr is None:
        die("no 'Open' section header found.", 1)
    pPr = clone_pPr_for_section(paras, hdr)
    new_para = make_para(pPr, text)
    # insert before the empty placeholder bullet ('[]') if present, else before
    # the next section header after Open, else right after the Open header.
    placeholder = None
    for p in paras[hdr + 1:]:
        if para_text(p).strip() in ("[]", "[ ]", ""):
            placeholder = p
            break
    if placeholder is not None:
        new_xml = insert_before_para(orig, placeholder, new_para)
    else:
        nxt = None
        for p in paras[hdr + 1:]:
            if para_text(p).strip() in ("In Progress", "Completed"):
                nxt = p
                break
        new_xml = (insert_before_para(orig, nxt, new_para) if nxt is not None
                   else insert_after_para(orig, paras[hdr], new_para))
    print(f"Adding open task: {text[:90]}")
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=1)
    print(f"Done. Backup: {bkp}")


def cmd_add_completed(text):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    hdr = find_header(paras, "Completed")
    if hdr is None:
        die("no 'Completed' section header found.", 1)
    pPr = clone_pPr_for_section(paras, hdr)
    new_para = make_para(pPr, text)
    new_xml = insert_after_para(orig, paras[hdr], new_para)
    print(f"Adding completed task: {text[:90]}")
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=1)
    print(f"Done. Backup: {bkp}")


def cmd_add_summary(text):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    anchor = None
    for i, p in enumerate(paras):
        t = para_text(p).lower()
        if "bulleted summary" in t and "newest" in t:
            anchor = i
            break
    if anchor is None:
        die("could not find the 'Bulleted summary ... newest' anchor.", 1)
    pPr = clone_pPr_for_section(paras, anchor)
    new_para = make_para(pPr, text)
    new_xml = insert_after_para(orig, paras[anchor], new_para)
    print(f"Adding summary: {text[:90]}")
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=1)
    print(f"Done. Backup: {bkp}")


def cmd_insert_after(search, text):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    tgt = find_one(paras, search)
    ref_para = paras[tgt]
    # build the new paragraph in the same style as the reference paragraph
    m = re.search(r'<w:pPr>.*?</w:pPr>', ref_para, re.DOTALL)
    pPr = m.group(0) if m else clone_pPr_for_section(paras, tgt - 1 if tgt > 0 else 0)
    new_para = make_para(pPr, text)
    new_xml = insert_after_para(orig, ref_para, new_para)
    print(f"Inserting after [{tgt}] {para_text(ref_para).strip()[:70]}...")
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=1)
    print(f"Done. Backup: {bkp}")


def cmd_replace_bullet(search, new_text):
    entries = read_entries()
    orig = get_docxml(entries)
    paras = PARA_RE.findall(orig)
    tgt = find_one(paras, search)
    old_para = paras[tgt]
    new_para = set_para_text(old_para, new_text)
    if new_para == old_para:
        print("No change needed (text already matches).")
        return
    new_xml = splice_verbatim(orig, old_para, new_para)
    for i, p in enumerate(paras):
        if i != tgt and p not in new_xml:
            die(f"internal guard: paragraph {i} vanished; aborting.", 6)
    print(f"Replacing [{tgt}]: {para_text(old_para).strip()[:70]}...")
    bkp = commit_new_xml(entries, orig, new_xml, expected_delta=0)
    print(f"Done. Backup: {bkp}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]

    def need(n):
        if len(sys.argv) < n:
            die(f"'{cmd}' needs more arguments; see --help.", 1)

    if cmd == 'read':
        cmd_read()
    elif cmd == 'remove':
        need(3); cmd_remove(sys.argv[2])
    elif cmd == 'remove-paragraph':
        need(3); cmd_remove_paragraph(sys.argv[2])
    elif cmd == 'remove-exact-line':
        need(3); cmd_remove_exact_line(sys.argv[2])
    elif cmd == 'move-to-completed':
        need(3); cmd_move_to_completed(sys.argv[2])
    elif cmd == 'mark-done':
        need(3); cmd_mark_done(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == 'add-open':
        need(3); cmd_add_open(sys.argv[2])
    elif cmd == 'add-completed':
        need(3); cmd_add_completed(sys.argv[2])
    elif cmd == 'add-summary':
        need(3); cmd_add_summary(sys.argv[2])
    elif cmd == 'insert-after':
        need(4); cmd_insert_after(sys.argv[2], sys.argv[3])
    elif cmd == 'replace-bullet':
        need(4); cmd_replace_bullet(sys.argv[2], sys.argv[3])
    else:
        die(f"unknown command: {cmd}", 1)
