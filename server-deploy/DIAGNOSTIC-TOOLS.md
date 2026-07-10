# CWO Diagnostic Tools

Local headless Chrome (via Puppeteer) tools for debugging live games.

## Prerequisites

- Node.js (any recent version)
- Puppeteer installed globally: `npm install -g puppeteer`

## Console Capture

Captures all browser console output including Scala `println()` traces compiled into main.js.

```
./cwo-console-capture.js <GAME_URL> [wait_seconds]
```

Default wait is 45 seconds (enough for most games to fully replay).

Example:
```
./cwo-console-capture.js https://cwo.freeddns.org/mnu/play/yqddoxxtvkoaiwpd 30
```

Output includes:
- `[LOG]` — println() traces from Scala code
- `[ERROR]` — resource load failures (404s, etc.)
- `[PAGE_ERROR]` — uncaught exceptions with full stack traces

### Workflow for debugging a crash

1. Add `println(s"[MY-TRACE] ...")` to the Scala source at suspect locations
2. Build with `sbt fullOptJS`
3. Deploy main.js to server (update cache tag in index.html)
4. Run: `./cwo-console-capture.js <game-url> > /tmp/trace_output.txt`
5. Grep the output for your trace prefix

## Game Log Extraction

Extracts the full player-visible game log (the formatted text a player sees in-browser).

```
./cwo-game-log.js <GAME_URL> [wait_seconds]
```

Example:
```
./cwo-game-log.js https://cwo.freeddns.org/play/yjvfukkqjbamdrlp > /tmp/gamelog.txt
```

Output is plain text (HTML tags stripped), ready for analysis.

## Notes

- Both tools run headless Chrome LOCALLY — no server-side chromium needed.
- The shebang uses `env -S` with NODE_PATH hardcoded to the global npm modules path.
  If node/nvm changes location, update the shebang.
- For games that crash during replay, the console capture will show `[PAGE_ERROR]` with
  the exception message and stack trace (minified line numbers, but still useful for
  identifying which handler crashed).
- Wait time should be long enough for the game to fully replay all actions. Large games
  (1000+ actions) may need 45-60 seconds. Small games work with 10-15 seconds.
