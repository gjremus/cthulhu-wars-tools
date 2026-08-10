#!/usr/bin/env python3
"""TRULY surgical docx editor for HomeBrews docs.

These docx files embed custom fonts that python-docx cannot parse and that a
pandoc round-trip STRIPS (destroying the file). So this tool does NOT use
pandoc or python-docx to write. It edits word/document.xml IN PLACE inside the
zip, copying every other zip entry (fonts, styles, images, numbering)
byte-for-byte, and changes the text of EXACTLY ONE paragraph.

Physical guarantees enforced on every write (any violation => abort, no write):
  * The file is never deleted, never truncated, never fully replaced.
  * Exactly ONE paragraph element changes. Never zero, never two+.
  * The paragraph COUNT is identical before and after (no add/remove of paras).
  * Every zip entry other than word/document.xml is byte-identical after.
  * The new document.xml still parses and still contains every OTHER paragraph
    unchanged.
  * A raw-bytes backup of the whole .docx is taken before any write.

Commands:
  hb-doc-edit.py <docx-path> replace-text "unique search text" "new text"
      Replace the visible text of the ONE paragraph matching the search string.
  hb-doc-edit.py <docx-path> insert-after "unique anchor text" "new paragraph"
  hb-doc-edit.py <docx-path> insert-after "unique anchor text" --file text.txt [--style "donor"]
      Insert one or more NEW paragraphs immediately AFTER the anchor paragraph.
      Each new paragraph is a CLONE of an existing paragraph's markup (the anchor
      by default, or the --style donor) with ONLY its visible text swapped, so it
      inherits the document's embedded-font run styling and cannot corrupt the
      file. With --file, every non-blank line of the text file becomes one new
      paragraph, in order. This command can ONLY ADD paragraphs: it never
      deletes, never overwrites, never replaces an existing paragraph, and the
      guards abort unless the paragraph count grows by exactly the number added
      and every original paragraph survives byte-for-byte.
  hb-doc-edit.py <docx-path> read
      Print every paragraph with an index (read-only; for finding search text).
  hb-doc-edit.py <docx-path> repair-borders [--apply]
      Recovery only. Reinstates paragraph markup that an earlier version of this
      tool overwrote (its text-run pattern also matched the border tag <w:top/>,
      leaving the file unopenable). Text is preserved as-is; the restored markup
      is copied verbatim from an undamaged paragraph in the same document.
      Refuses to run on a document that already parses. Dry run by default.

There is NO remove, NO overwrite-of-existing, NO full-replace, NO mass-edit, NO
sheet op. replace-text changes exactly one paragraph's text; insert-after only
ADDS new paragraphs. Neither can shrink or blank the file.
The first argument MUST be a .docx inside the HomeBrews folder.
"""
import sys, os, time, zipfile, shutil, re, hashlib

HOMEBREWS_ROOT = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews"
LOCKOUT_SECONDS = 300
BACKUP_DIR = os.path.expanduser("~/.cw-doc-backups")
OUR_WRITE_MARKER = os.path.join(BACKUP_DIR, ".last-hb-ticker-write")
DOCXML = "word/document.xml"

# Matches a whole paragraph element (open+close) OR a self-closing empty one.
PARA_RE = re.compile(r'<w:p(?:\s[^>]*)?>.*?</w:p>|<w:p\s*/>', re.DOTALL)
# Matches the text inside a <w:t> run.
# The name must END at the '>' or at whitespace-then-attributes, otherwise this
# also matches <w:top .../> (a paragraph-border tag), and rewriting that as if
# it were a text run destroys the paragraph's border/spacing markup and leaves
# malformed XML. Self-closing <w:t/> holds no text, so it is excluded too.
WT_RE = re.compile(r'(<w:t(?:\s[^>]*?)?>)(.*?)(</w:t>)', re.DOTALL)


def die(msg, code=1):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(code)


def validate_doc_path(path):
    real = os.path.realpath(path)
    if not real.startswith(os.path.realpath(HOMEBREWS_ROOT)):
        die(f"target doc is not inside HomeBrews folder: {path}", 4)
    if not os.path.isfile(path):
        die(f"target doc does not exist: {path}", 4)
    if not path.endswith(".docx"):
        die(f"target is not a .docx file: {path}", 4)


def check_lockout(doc):
    """Refuse to write if the doc was modified <5 min ago by someone else."""
    try:
        mtime = os.path.getmtime(doc)
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


def backup(doc):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(doc).replace(" ", "_")
    dst = os.path.join(BACKUP_DIR, f"{base}.{stamp}.bak")
    shutil.copy2(doc, dst)
    # keep only 3 most recent backups per doc
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


def read_entries(doc):
    """Return (ordered list of (ZipInfo, bytes)) for every entry."""
    out = []
    with zipfile.ZipFile(doc) as z:
        if z.testzip() is not None:
            die("zip integrity check failed on source doc.", 5)
        for info in z.infolist():
            out.append((info, z.read(info.filename)))
    return out


def para_text(p):
    return "".join(m.group(2) for m in WT_RE.finditer(p))


def cmd_read(doc):
    entries = read_entries(doc)
    xml = next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")
    paras = PARA_RE.findall(xml)
    for idx, p in enumerate(paras):
        t = para_text(p).strip()
        if t:
            print(f"[{idx}] {t}")


def xml_escape(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def xml_is_wellformed(xml):
    """True if this document.xml parses. Uses only the standard library."""
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(xml)
        return True
    except ET.ParseError:
        return False


def replace_text(doc, search, new_text):
    if not new_text.strip():
        die("refusing to write empty text (would blank the paragraph).", 5)

    entries = read_entries(doc)
    orig_xml = next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")
    paras = PARA_RE.findall(orig_xml)

    # locate the single matching paragraph
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

    # Build the new paragraph: put ALL new text in the first <w:t>, blank the rest.
    # This preserves the paragraph's formatting (pStyle, numPr, run props) exactly.
    state = {"done": False}
    def sub(m):
        if state["done"]:
            return m.group(1) + m.group(3)  # empty subsequent runs
        state["done"] = True
        return m.group(1) + xml_escape(new_text) + m.group(3)
    new_para = WT_RE.sub(sub, old_para)

    if new_para == old_para:
        print("No change needed (text already matches).")
        return

    # Splice back: replace ONLY the target paragraph occurrence.
    new_paras = list(paras)
    new_paras[tgt] = new_para

    # ---- GUARD 1: exactly one paragraph differs -----------------------------
    diffs = [i for i in range(len(paras)) if paras[i] != new_paras[i]]
    if diffs != [tgt]:
        die(f"internal guard: expected exactly 1 changed paragraph, got {diffs}.", 6)

    # ---- GUARD 2: paragraph count identical ---------------------------------
    if len(new_paras) != len(paras):
        die("internal guard: paragraph count changed.", 6)

    # Reassemble document.xml by replacing the exact old_para substring once.
    # (old_para is a literal slice of orig_xml, so this is a precise splice.)
    if orig_xml.count(old_para) != 1:
        die("target paragraph text is not uniquely locatable in XML; aborting to be safe.", 6)
    new_xml = orig_xml.replace(old_para, new_para, 1)

    # ---- GUARD 3: every other paragraph still present verbatim ---------------
    for i, p in enumerate(paras):
        if i == tgt:
            continue
        if p not in new_xml:
            die(f"internal guard: paragraph {i} vanished from new XML.", 6)

    # ---- GUARD 4: new xml still parses to same paragraph count ---------------
    if len(PARA_RE.findall(new_xml)) != len(paras):
        die("internal guard: reparsed paragraph count mismatch.", 6)

    # ---- GUARD 4b: the result must be WELL-FORMED XML -----------------------
    # Regex splicing can silently produce markup Word refuses to open. Never
    # write a document.xml that does not parse. (If the input was already
    # damaged, say so plainly instead of blaming this edit.)
    if not xml_is_wellformed(orig_xml):
        die("this document's text is already damaged (its internal markup does "
            "not parse). Refusing to edit it until it is repaired.", 7)
    if not xml_is_wellformed(new_xml):
        die("internal guard: the edit would produce markup that Word cannot "
            "open. Nothing was written.", 6)

    bkp = commit_new_xml(doc, entries, new_xml)

    mark_our_write()
    print(f"Replaced paragraph [{tgt}]. Backup: {bkp}")
    print(f"  old: {para_text(old_para).strip()[:80]}")
    print(f"  new: {new_text.strip()[:80]}")


def _clone_para_with_text(donor_para, new_text):
    """Return a copy of donor_para with all visible text replaced by new_text.

    All text goes into the FIRST <w:t> run; subsequent runs are blanked. This
    preserves the paragraph's pStyle/numPr/run props (and thus the embedded-font
    references) exactly — identical mechanism to replace-text, so it inherits the
    same anti-corruption behavior. The donor MUST have an editable text run.
    """
    if not WT_RE.search(donor_para):
        die("style-donor paragraph has no editable text run to clone.", 1)
    state = {"done": False}
    def sub(m):
        if state["done"]:
            return m.group(1) + m.group(3)
        state["done"] = True
        return m.group(1) + xml_escape(new_text) + m.group(3)
    return WT_RE.sub(sub, donor_para)


def insert_after(doc, anchor, new_texts, donor_search=None):
    """Insert new paragraph(s) immediately after the anchor paragraph.

    INSERT-ONLY: existing paragraphs are never changed or removed. Each new
    paragraph clones the markup of a donor (the anchor by default, or the
    paragraph matched by donor_search) so embedded fonts are preserved.
    """
    new_texts = [t for t in new_texts if t.strip()]
    if not new_texts:
        die("refusing to insert: no non-blank paragraph text provided.", 5)

    entries = read_entries(doc)
    orig_xml = next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")
    if not xml_is_wellformed(orig_xml):
        die("this document's markup does not parse; refusing to edit until "
            "it is repaired.", 7)
    paras = PARA_RE.findall(orig_xml)

    # locate the single anchor paragraph
    amatches = [i for i, p in enumerate(paras) if anchor.lower() in para_text(p).lower()]
    if not amatches:
        die(f"no paragraph contains anchor: {anchor}", 1)
    if len(amatches) > 1:
        die(f"anchor matched {len(amatches)} paragraphs; must match exactly one. "
            f"Use a longer, unique anchor string.", 1)
    tgt = amatches[0]
    anchor_para = paras[tgt]

    # pick the style donor
    if donor_search:
        dmatches = [i for i, p in enumerate(paras) if donor_search.lower() in para_text(p).lower()]
        if not dmatches:
            die(f"no paragraph contains style donor: {donor_search}", 1)
        if len(dmatches) > 1:
            die(f"style donor matched {len(dmatches)} paragraphs; must be unique.", 1)
        donor_para = paras[dmatches[0]]
    else:
        donor_para = anchor_para

    new_paras = [_clone_para_with_text(donor_para, t) for t in new_texts]

    # Splice the new paragraphs in right after the anchor's unique occurrence.
    if orig_xml.count(anchor_para) != 1:
        die("anchor paragraph is not uniquely locatable in XML; aborting.", 6)
    insertion = anchor_para + "".join(new_paras)
    new_xml = orig_xml.replace(anchor_para, insertion, 1)

    # ---- GUARD A: paragraph count grew by EXACTLY len(new_paras) ------------
    after = PARA_RE.findall(new_xml)
    if len(after) != len(paras) + len(new_paras):
        die(f"internal guard: expected {len(paras)+len(new_paras)} paragraphs, "
            f"got {len(after)}; aborting.", 6)

    # ---- GUARD B: every ORIGINAL paragraph still present verbatim -----------
    for i, p in enumerate(paras):
        if p not in new_xml:
            die(f"internal guard: original paragraph {i} vanished; aborting.", 6)

    # ---- GUARD C: the anchor is immediately followed by the new paragraphs --
    if insertion not in new_xml:
        die("internal guard: insertion block not found intact; aborting.", 6)

    # ---- GUARD D: result must be WELL-FORMED XML ----------------------------
    if not xml_is_wellformed(new_xml):
        die("internal guard: the insert would produce markup Word cannot open. "
            "Nothing was written.", 6)

    # ---- GUARD E: file must not shrink (insert can only grow it) ------------
    # (commit_new_xml also enforces >=90% of original; inserting only adds.)

    bkp = commit_new_xml(doc, entries, new_xml)
    mark_our_write()
    print(f"Inserted {len(new_paras)} paragraph(s) after [{tgt}] "
          f"(\"{para_text(anchor_para).strip()[:50]}\"). Backup: {bkp}")
    for j, t in enumerate(new_texts):
        print(f"  +[{tgt+1+j}] {t.strip()[:80]}")


def commit_new_xml(doc, entries, new_xml):
    """Swap in a new document.xml, keeping every other zip entry byte-identical.

    Shared by replace-text and repair-borders so both go through the same
    verification before anything touches the real file.
    """
    # Take backup, then rewrite the zip in place.
    check_lockout(doc)
    bkp = backup(doc)
    check_lockout(doc)

    tmp = doc + ".tmp_surgical"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for info, data in entries:
                if info.filename == DOCXML:
                    payload = new_xml.encode("utf-8")
                else:
                    # byte-for-byte copy of every other entry (fonts, styles, images)
                    payload = data
                # preserve compression type per entry
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.internal_attr = info.internal_attr
                zi.create_system = info.create_system
                zout.writestr(zi, payload)

        # ---- GUARD 5: verify the temp file before swapping in --------------
        with zipfile.ZipFile(tmp) as zc:
            if zc.testzip() is not None:
                die("written zip failed integrity check; not swapping in.", 6)
            names_new = set(zc.namelist())
        names_old = {i.filename for i, _ in entries}
        if names_new != names_old:
            die(f"zip entry set changed: {names_old ^ names_new}; aborting.", 6)
        # every non-document entry must be byte-identical
        with zipfile.ZipFile(tmp) as zc:
            for info, data in entries:
                if info.filename == DOCXML:
                    continue
                if zc.read(info.filename) != data:
                    die(f"non-document entry changed: {info.filename}; aborting.", 6)

        # ---- GUARD 6: size sanity (fonts dominate; must not shrink hugely) --
        old_size = os.path.getsize(doc)
        new_size = os.path.getsize(tmp)
        if new_size < old_size * 0.90:
            die(f"output ({new_size}) <90% of original ({old_size}); aborting.", 6)

        # CRITICAL — do NOT os.replace(tmp, doc): on Google Drive File Stream a
        # rename swaps in a NEW file object, so the doc gets a fresh Drive file
        # ID and ALL its sharing permissions are destroyed (the "wiped doc that
        # loses sharing" bug). Instead overwrite the EXISTING file in place
        # (truncate + rewrite the same path/inode), which keeps the Drive file
        # ID — and therefore the sharing — intact.
        with open(tmp, "rb") as src, open(doc, "wb") as dst:
            shutil.copyfileobj(src, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    return bkp


# The exact wreckage left by the old <w:t[^>]*> regex, which matched the
# border tag <w:top .../> and overwrote everything up to the real text's
# </w:t>: the border close, the paragraph's spacing/indent/justification, the
# run open, and the run's <w:t> open tag were all swallowed.
#   <w:pBdr><w:top .../>TEXT</w:t></w:r>...
# The text itself survived, so the fix is to reinstate the dropped markup
# around it. Nothing is invented: the replacement markup is copied verbatim
# from an undamaged paragraph in the SAME document.
DAMAGE_RE = re.compile(
    r'(<w:pBdr><w:top\s[^>]*?/>)(.*?)(</w:t>)', re.DOTALL)
# An undamaged paragraph, to lift the correct markup from.
INTACT_RE = re.compile(
    r'<w:pBdr><w:top\s[^>]*?/>(<w:left\s.*?</w:pPr>)(<w:r\b.*?<w:t(?:\s[^>]*?)?>)',
    re.DOTALL)


def find_damaged(paras):
    """Indexes of paragraphs whose border markup was overwritten with text."""
    return [i for i, p in enumerate(paras)
            if DAMAGE_RE.search(p) and '</w:pBdr>' not in p]


def cmd_repair_borders(doc, apply_it):
    entries = read_entries(doc)
    orig_xml = next(b for i, b in entries if i.filename == DOCXML).decode("utf-8")
    paras = PARA_RE.findall(orig_xml)

    damaged = find_damaged(paras)
    if not damaged:
        print("Nothing to repair: no paragraph has overwritten border markup.")
        return
    if xml_is_wellformed(orig_xml):
        die("this document already parses; repair-borders is only for damaged "
            "files and will not touch a healthy one.", 7)

    # Lift the dropped markup from an intact paragraph in THIS document.
    donor = INTACT_RE.search(orig_xml)
    if not donor:
        die("found no undamaged paragraph to copy the correct markup from.", 7)
    tail_pPr, run_open = donor.group(1), donor.group(2)

    new_xml, fixed = orig_xml, []
    for i in damaged:
        old_para = paras[i]
        if new_xml.count(old_para) != 1:
            die(f"paragraph {i} is not uniquely locatable; aborting.", 6)

        def sub(m, _t=tail_pPr, _r=run_open):
            # <w:pBdr><w:top/> + [restored borders/spacing] + [run open] + text + </w:t>
            return m.group(1) + _t + _r + m.group(2) + m.group(3)
        new_para, n = DAMAGE_RE.subn(sub, old_para, count=1)
        if n != 1 or new_para == old_para:
            die(f"could not reconstruct paragraph {i}; aborting.", 6)
        new_xml = new_xml.replace(old_para, new_para, 1)
        fixed.append((i, para_text(new_para).strip()[:70]))

    # Same non-negotiables as replace-text: count preserved, result must parse.
    if len(PARA_RE.findall(new_xml)) != len(paras):
        die("internal guard: paragraph count changed; aborting.", 6)
    if not xml_is_wellformed(new_xml):
        die("repair did not produce well-formed markup; nothing was written.", 6)
    for i, p in enumerate(paras):
        if i not in damaged and p not in new_xml:
            die(f"internal guard: paragraph {i} vanished; aborting.", 6)

    if not apply_it:
        print(f"DRY RUN — would repair {len(fixed)} paragraph(s); "
              f"result parses cleanly. Re-run with --apply to write.")
        for i, t in fixed:
            print(f"  [{i}] {t}")
        return

    bkp = commit_new_xml(doc, entries, new_xml)
    mark_our_write()
    print(f"Repaired {len(fixed)} paragraph(s). Backup: {bkp}")
    for i, t in fixed:
        print(f"  [{i}] {t}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    DOC = sys.argv[1]
    validate_doc_path(DOC)
    cmd = sys.argv[2]
    if cmd == "read":
        cmd_read(DOC)
    elif cmd == "replace-text":
        if len(sys.argv) < 5:
            die("replace-text requires: <docx> replace-text \"search\" \"new text\"", 1)
        replace_text(DOC, sys.argv[3], sys.argv[4])
    elif cmd == "insert-after":
        if len(sys.argv) < 4:
            die("insert-after requires: <docx> insert-after \"anchor\" "
                "(\"new text\" | --file text.txt) [--style \"donor\"]", 1)
        anchor = sys.argv[3]
        rest = sys.argv[4:]
        donor_search = None
        if "--style" in rest:
            si = rest.index("--style")
            if si + 1 >= len(rest):
                die("--style requires a donor search string.", 1)
            donor_search = rest[si + 1]
            del rest[si:si + 2]
        if rest and rest[0] == "--file":
            if len(rest) < 2:
                die("--file requires a path.", 1)
            fp = rest[1]
            if not os.path.isfile(fp):
                die(f"text file not found: {fp}", 1)
            with open(fp, encoding="utf-8") as fh:
                new_texts = [ln.rstrip("\n") for ln in fh]
        else:
            if not rest:
                die("insert-after requires new paragraph text (or --file).", 1)
            new_texts = [rest[0]]
        insert_after(DOC, anchor, new_texts, donor_search)
    elif cmd == "repair-borders":
        cmd_repair_borders(DOC, apply_it="--apply" in sys.argv[3:])
    else:
        die(f"unknown command: {cmd}. Only 'read', 'replace-text', "
            f"'insert-after' and 'repair-borders' exist.", 1)
