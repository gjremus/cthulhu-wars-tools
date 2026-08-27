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
import sys, os, time, zipfile, shutil, re, hashlib, tempfile
import docguard_lock  # unlock()/relock() the OS immutable flag around our write

HOMEBREWS_ROOT = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Factions/HomeBrews"
LOCKOUT_SECONDS = 300
BACKUP_DIR = os.path.expanduser("~/.cw-doc-backups")
OUR_WRITE_MARKER = os.path.join(BACKUP_DIR, ".last-hb-ticker-write")
DOCXML = "word/document.xml"

# A Google Drive numbered conflict copy is named "<base> (1).docx", "<base> (2).docx".
# These are NEVER a valid edit target, and their mere presence means the document
# has forked — editing anything then multiplies the divergence.
NUMBERED_COPY_RE = re.compile(r'^(?P<stem>.+?) \(\d+\)$')

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
    if is_numbered_copy(path):
        die(f"target is a Google Drive conflict copy ('(N)' in the name): {path}. "
            f"These are NEVER valid and must never be read or written. Only the "
            f"single original file may be used.", 4)


def is_numbered_copy(path):
    """True if `path` looks like a Google Drive conflict copy: '<base> (N).docx'."""
    stem = os.path.basename(path)
    if stem.endswith(".docx"):
        stem = stem[:-5]
    return bool(NUMBERED_COPY_RE.match(stem))


def find_conflict_copies(doc):
    """Return sibling '(N)' conflict copies of `doc` in the same folder.

    Their existence means Google Drive forked this document; editing anything
    while they exist multiplies the divergence into further copies.
    """
    folder = os.path.dirname(os.path.realpath(doc))
    base = os.path.basename(doc)
    if base.endswith(".docx"):
        base = base[:-5]
    m = NUMBERED_COPY_RE.match(base)
    canon = m.group("stem") if m else base   # base name with any " (N)" stripped
    out = []
    try:
        names = os.listdir(folder)
    except OSError:
        return out
    for f in names:
        if not f.endswith(".docx"):
            continue
        mm = NUMBERED_COPY_RE.match(f[:-5])
        if mm and mm.group("stem") == canon:
            out.append(os.path.join(folder, f))
    return out


def warn_conflict_copies(doc):
    """Warn (do NOT block) if any '(N)' conflict copy of this doc exists.

    We ALWAYS edit the single un-numbered original — that is the only valid file,
    and validate_doc_path already hard-refuses (exit 4) any attempt to target a
    numbered copy. The numbered copies themselves are never read or written by
    this tool, and staging happens outside the Drive folder, so editing the
    original cannot create or grow them. We surface their presence on stderr so
    the caller can notify the owner to delete the strays, but we do NOT refuse the
    edit: blocking here would stop legitimate work on the original whenever Drive
    leaves a fork behind.
    """
    sibs = find_conflict_copies(doc)
    if sibs:
        listing = "; ".join(sorted(os.path.basename(s) for s in sibs))
        print("WARNING: Google Drive conflict copies present (" + listing + "). "
              "Editing the single original only; these numbered copies are never "
              "touched. Owner should delete them — only the original is valid.",
              file=sys.stderr)


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


# Exit code 3 == Google Drive is actively syncing this file right now.
# Distinct from LOCKOUT (2, "a human edited it recently"). The caller (ticker)
# treats code 3 as: wait 5 min and retry; keep retrying; if it persists ~1 hour,
# record a row in the task docs and alert — but NEVER delete/move/copy the file.
DRIVE_BUSY = 3


def check_drive_sync(doc):
    """Refuse to write while Google Drive File Stream is mid-sync on this file.

    Writing (even a safe in-place truncate+rewrite) into the exact window where
    Drive is streaming the file down/up makes Drive's conflict resolver keep one
    version, spawn numbered "(1)"/"(2)" conflicted copies, and move the version
    it deems superseded — the user's open working copy — into the Trash. The
    script itself never trashes anything; this guard simply declines to write
    during that unsafe window so Drive is never given a conflict to resolve.

    Detection: sample (size, mtime) twice a short interval apart. If either
    changes, Drive is actively writing the file, so we back off. Stable across
    the window == safe to write.
    """
    try:
        s1 = os.stat(doc)
    except OSError:
        return  # nothing to guard; downstream will fail cleanly
    time.sleep(1.5)
    try:
        s2 = os.stat(doc)
    except OSError:
        die("file vanished while checking for Drive sync; aborting, will retry.",
            DRIVE_BUSY)
    if (s1.st_size, int(s1.st_mtime)) != (s2.st_size, int(s2.st_mtime)):
        die("Google Drive is actively syncing this file (size/mtime changing). "
            "Not writing into a live sync; will retry.", DRIVE_BUSY)


def backup(doc):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(doc).replace(" ", "_")
    dst = os.path.join(BACKUP_DIR, f"{base}.{stamp}.bak")
    shutil.copy2(doc, dst)
    # copy2/copystat may have carried the source's immutable flag onto the .bak;
    # our own backups must stay mutable so the prune below can remove old ones.
    docguard_lock.unlock(dst)
    # keep only 3 most recent backups per doc. This is LEGITIMATE cleanup of our
    # OWN private backup copies inside BACKUP_DIR — it is expected and correct,
    # and it is NOT what put the real guide in the Trash. (That was Google
    # Drive's conflict resolver reacting to an in-place write during a live sync;
    # see check_drive_sync + the write block in commit_new_xml.) These pruned
    # files are our .bak copies only; we hard-refuse to touch anything outside
    # BACKUP_DIR, and we never move to Trash — we os.remove within our own dir.
    same = sorted(
        [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
         if f.startswith(base + ".") and f.endswith(".bak")],
        key=os.path.getmtime, reverse=True)
    real_backup_dir = os.path.realpath(BACKUP_DIR)
    for old in same[3:]:
        # Safety: only ever remove a file that physically lives inside BACKUP_DIR.
        if os.path.realpath(os.path.dirname(old)) != real_backup_dir:
            continue
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


def _force_materialize(path, tries=30, delay=8):
    """Google Drive keeps files as 'dataless' placeholders and only downloads the
    real bytes when the WHOLE file is read to EOF. zipfile.ZipFile seeks to the
    central directory (a partial read) and fails 'not a zip' on a dataless file,
    so we do a full read first to force Drive's on-demand fetch. Not corruption,
    does not modify the file. (Verified 2026-08-26: partial read -> empty stub;
    full read -> all bytes + file flips to materialized.)"""
    import time
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


def read_entries(doc):
    """Return (ordered list of (ZipInfo, bytes)) for every entry."""
    _force_materialize(doc)
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
    warn_conflict_copies(doc)
    check_lockout(doc)
    check_drive_sync(doc)
    bkp = backup(doc)
    check_lockout(doc)
    check_drive_sync(doc)

    # Stage the rebuilt zip OUTSIDE the Google Drive folder (in our local backup
    # dir). Writing a large temp file *inside* the synced Drive folder — even one
    # we delete right away — hands Drive a transient file to sync and is itself a
    # source of "(N)" conflicted copies. Building it on local disk and copying the
    # bytes into the existing file in place avoids giving Drive anything new to fork.
    os.makedirs(BACKUP_DIR, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".tmp_surgical", dir=BACKUP_DIR)
    os.close(fd)
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
        #
        # One more Drive-sync + conflict-copy check immediately before the write:
        # this is the narrowest possible window, so re-checking here (not just at
        # entry) is what actually prevents the conflicted-copy / file-to-Trash event.
        check_drive_sync(doc)
        pre_ino = os.stat(doc).st_ino
        # The doc is OS-locked (uchg) against all deletion/overwrite. Lift the
        # flag ONLY for the in-place write, then restore it in the finally below
        # so it is never left writable — even if the write raises.
        _was_locked = docguard_lock.unlock(doc)
        try:
            with open(tmp, "rb") as src, open(doc, "wb") as dst:
                shutil.copyfileobj(src, dst)
        finally:
            if _was_locked:
                docguard_lock.relock(doc)
        # Post-write proof the in-place overwrite kept the SAME file object
        # (same inode == same Drive file ID == sharing preserved, no conflicted
        # copy). If the inode changed, Drive swapped the file underneath us mid
        # write — surface it so the caller retries rather than trusting a write
        # that may have spawned a "(1)"/"(2)" copy.
        post_ino = os.stat(doc).st_ino
        if pre_ino != post_ino:
            die("file identity (inode) changed during write — Drive may have "
                "swapped/conflicted the file; will retry. The original is "
                "untouched by this script (backup: " + str(bkp) + ").",
                DRIVE_BUSY)
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
