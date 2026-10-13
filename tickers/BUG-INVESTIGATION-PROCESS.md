# Bug Investigation & Fixing Process

This is the standard process for investigating and fixing bugs in Cthulhu Wars Online. Follow this order to avoid wasted time and token burn.

## 1. GATHER EVIDENCE FIRST (Don't Code Yet)

### For Crash/Server Bugs:
1. **Check Java Console Log** on the server:
   ```bash
   ssh oracle-cw-server@cwo.freeddns.org "tail -200 /opt/cwo/logs/console.log"
   ```
   Look for exceptions, stack traces, errors near the crash time.

2. **Check Game Log** if there's a specific game involved:
   ```bash
   ssh oracle-cw-server@cwo.freeddns.org "cat /opt/cwo/logs/game-<ID>.log"
   ```

3. **Pull Server Stats** if performance-related:
   ```bash
   ssh oracle-cw-server@cwo.freeddns.org "cat /opt/cwo/logs/server-stats.json"
   ```

### For UI/Frontend Bugs:
1. **Test in Headless Chrome**:
   ```bash
   ~/Claude-Projects/cthulhu-wars-tools/test-chrome-headless.sh
   ```
   Check console output for JavaScript errors.

2. **Don't analyze minified JS** - trace the Scala source instead.

### For Gameplay Bugs:
1. **Get the game log** from the user or server
2. **Load it for local replay** to reproduce:
   ```bash
   # Copy game log from server to local test rig
   scp oracle-cw-server:/opt/cwo/logs/game-<ID>.log ~/test-game.log
   ```

## 2. TIME-BOXED ANALYSIS (5 Minutes Max)

Spend **no more than 5 minutes** reading code to understand the bug.

If you can't find the issue in 5 minutes, STOP analyzing and move to Step 3 (Trace).

**Why:** Circular debugging (>15min of reading code) wastes tokens and time. Traces give you facts.

## 3. ADD TRACES (Don't Loop on Analysis)

If the bug isn't obvious after 5 minutes, add targeted logging:

```scala
// In the suspected code path
println(s"[TRACE] ActionName: variable=$value, state=$state")
```

1. Add traces around the suspected area
2. Compile locally
3. If gameplay bug: use local replay test rig to replay the game log
4. If crash bug: start a test game or reproduce the crash scenario
5. Read the trace output to see what actually happened

**Local Replay Test Rig** (for gameplay bugs):
- Patch the local build with traces
- Replay the game log from the bug report
- Diff the output to see where behavior diverges
- Location: `~/Claude-Projects/cthulhu-wars-Main/` with patched Game.scala

## 4. FIX THE BUG

Once you know the root cause from traces/logs:

1. **Write the fix** in the appropriate build:
   - Main bugs: `~/Claude-Projects/cthulhu-wars-Main/`
   - Homebrew bugs: `~/Claude-Projects/cw-homebrew-wt/`
   - Library bugs: `~/Claude-Projects/cw-homebrew-library/`

2. **Test locally first**:
   - Compile: `sbt solo/fullLinkJS`
   - If gameplay: replay the bug game log again with the fix
   - If UI: test in headless Chrome
   - Verify the bug is gone

3. **If live game data needs fixing**: ASK THE USER FIRST
   - Never touch live games without explicit permission
   - Back up the game log before any surgery
   - Document what you changed in the rollback log

## 5. DEPLOY THE FIX

### For Code Changes:

**Main Build:**
```bash
# 1. Sonnet agent commits & pushes
~/Claude-Projects/cthulhu-wars-tools/scripts/git-push-summary.sh \
  ~/Claude-Projects/cthulhu-wars-Main \
  "Fix: <short title>" \
  "<what changed and why>" \
  <changed files>

# 2. Sonnet agent deploys
~/Claude-Projects/cthulhu-wars-tools/server-deploy/deploy-mnu-to-vm.sh
```

**Homebrew Build:**
```bash
# 1. Sonnet agent commits & pushes
~/Claude-Projects/cthulhu-wars-tools/scripts/git-push-summary.sh \
  ~/Claude-Projects/cw-homebrew-wt \
  "Fix: <short title>" \
  "<what changed and why>" \
  <changed files>

# 2. Sonnet agent deploys
~/Claude-Projects/cthulhu-wars-tools/server-deploy/deploy-hb-to-vm.sh
```

**Add --assets flag** if images changed.

### For Live Game Surgery:
1. Back up the game first
2. Use surgical edit scripts (if they exist for this case)
3. Document in the appropriate rollback log

## 6. VERIFY THE FIX

1. **Check deployment worked**:
   ```bash
   ssh oracle-cw-server@cwo.freeddns.org "ls -lh /opt/cwo/<build>/solo-opt.js"
   ```
   File timestamp should be recent.

2. **Test live in browser**:
   - Load the game in headless Chrome or real browser
   - Check JavaScript console for errors
   - Verify the bug scenario no longer reproduces

3. **Check game log** after testing live:
   ```bash
   ssh oracle-cw-server@cwo.freeddns.org "tail -50 /opt/cwo/logs/game-<ID>.log"
   ```

## 7. DOCUMENT THE FIX

**For Homebrew fixes:**
- Haiku agent adds entry to master rollback log
- Use surgical `hb-doc-edit.py` (never replace full doc)

**For bug reports from designer:**
- Update the bug history entry with what was fixed

## Special Cases

### "No Live Game Exists Yet"
If bug happens before game starts:
1. Ask user to start an online game and provide the game name/ID
2. Once started, pull the game log and trace the startup sequence
3. Add traces around game initialization code

### "Crash on Game Start"
If crash prevents game from starting:
1. Add traces in initialization code (Game.scala, startup sequence)
2. Check Java console log for the exception
3. Test locally with a minimal game start scenario
4. Deploy fix and verify startup works

### "Intermittent/Rare Bug"
If bug doesn't always happen:
1. Add permanent traces (not println, use proper logging)
2. Deploy and ask user to play until it happens again
3. Collect the game log when it reproduces
4. Analyze the traces to see what was different

## Key Rules

- **Start with logs/traces, not code analysis** (feedback_start_with_logs_traces)
- **5 minute analysis cap** before adding traces (feedback_5min_code_analysis_max)
- **Don't loop on analysis >15min** (feedback_trace_dont_analyze)
- **Headless Chrome for UI bugs** (feedback_headless_chrome_debug)
- **Never touch live games without permission** (feedback_never_touch_live_games)
- **Always verify after deploy** (feedback_verify_deploy)
- **Use local replay test rig** for gameplay bugs (reference_local_replay_test_rig)

## File Locations

- **Java Console Log**: `/opt/cwo/logs/console.log` on server
- **Game Logs**: `/opt/cwo/logs/game-<ID>.log` on server
- **Server Stats**: `/opt/cwo/logs/server-stats.json` on server
- **Deployed Builds**:
  - Main: `/opt/cwo/mnu/` on server
  - Homebrew: `/opt/cwo/hb/` on server
  - Library: `/opt/cwo/library/` on server
- **Local Test Rig**: `~/Claude-Projects/cthulhu-wars-Main/` (patched for replay)
- **Rollback Logs**: `~/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/deployment-general/`
