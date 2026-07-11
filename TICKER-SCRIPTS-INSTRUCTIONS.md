## Ticker Python Scripts — What They Are and How They Work

### Location
All ticker scripts live in `/Users/gremus/Claude-Projects/cthulhu-wars-tools/scripts/`.

### Naming Convention
- `master_tick_writer_HHMM_MMDD.py` — writes to the master current tasks doc
- `library_tick_writer_HHMM_MMDD.py` — writes to the Library at Celaeno task doc
- `backup_tick_writer_HHMM_MMDD.py` — fallback ticker writes (same format)
- `fbe_tick_YYYYMMDD_HHMM.py` — faction-specific ticker writes

### What They Do
Each script is a one-shot Python program that edits a `.docx` file using `python-docx`. A script typically:
1. Opens the target docx
2. Locates sections by heading text (Open, In Progress, Completed, Bulleted summary, etc.)
3. Modifies bullet text (update markers, move items between sections, add summary lines)
4. Saves the docx back

### How They Are Run
Scripts are never run directly. They are always invoked via the safe-write guard:
```
/Users/gremus/Claude-Projects/cthulhu-wars-tools/scripts/safe-docx-write.sh "<target.docx>" "python3 <script.py>"
```

### Mandatory Requirements

Every ticker script MUST:

1. **Check for ANY changes to the doc** — Before reading the doc, verify its mtime is older than 5 minutes. The `safe-docx-write.sh` wrapper enforces this, but the script itself should also validate state hasn't changed between read and write.

2. **Check EVERY open task** — The script must iterate all paragraphs between the "Open" and "In Progress" section headers and act on each one. Never skip tasks or assume there's nothing to do.

3. **Make a BACKUP COPY immediately before editing** — The `safe-docx-write.sh` wrapper handles this (creates `/tmp/safe-docx-backup-TIMESTAMP.docx`), but if running outside the wrapper, the script must `cp` the file first.

4. **Check AGAIN for changes immediately before editing** — Right before calling `d.save()`, re-check the file's mtime/hash. The wrapper's pre/post watch handles the TOCTOU gap, but scripts should not hold the file open for extended periods between read and write.

### The Safe Write Guard (`safe-docx-write.sh`)
Located at `/Users/gremus/Claude-Projects/cthulhu-wars-tools/scripts/safe-docx-write.sh`. It enforces:
- 5-minute mtime lockout (rejects if file was edited < 5 min ago)
- Content hash check (catches Google Drive sync race conditions)
- 5-second pre-write watch (aborts if file changes during watch)
- Lockfile (prevents concurrent writers)
- Raw-bytes backup to `/tmp/`
- Final mtime re-check (TOCTOU closure)
- 5-second post-write watch (verifies write landed)
- Saves new content hash for next run's comparison

### Keep at Most 2-3 Backup Copies
Old backups in `/tmp/safe-docx-backup-*.docx` should be pruned. Move older ones to `~/.Trash/` — never `rm`.
