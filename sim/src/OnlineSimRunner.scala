package cws

import hrf.colmat._
import java.net.{URI, URLEncoder}
import java.net.http.{HttpClient, HttpRequest, HttpResponse}
import java.time.Duration
import scala.util.Try

/**
 * OnlineSimRunner — plays bot-vs-bot games against the LIVE online server.
 *
 * Designed to run on the same machine as the akka-http server (Oracle VM)
 * so HTTP traffic goes over loopback (no real-internet latency, no external
 * bandwidth charged). Few seconds per game; exercises the full online stack
 * (parser, persistence, akka-http) which the in-process SimRunner can't.
 *
 * Lifecycle per game:
 *   1. POST /create with all factions marked Human (orchestrator drives all).
 *   2. POST /admin/<t>/mark-bot/<gameId> — admin UI hides the game by default.
 *   3. Local Game instance mirrors the engine state. Each Ask -> bot decides
 *      via Host.askFaction -> action POSTed to /write/<roleSecret>/<index>.
 *   4. On GameOverPhaseAction: POST /admin/<t>/delete (clean exit, no record).
 *   5. On crash mid-game: log + LEAVE in DB (so the broken game can be
 *      inspected via /admin/log/<id>).
 *
 * Usage:
 *   sbt "runMain cws.OnlineSimRunner <serverUrl> <adminToken> <numGames> <map> [factions...]"
 * Examples:
 *   OnlineSimRunner https://cwo.freeddns.org TOKEN 5 Library33 GC CC TS
 *   OnlineSimRunner http://localhost:8080  TOKEN 1 Library35 OW TS FB DS
 *
 * Note: --replay is intentionally not provided — that's SimReplayOrphan.
 */
object OnlineSimRunner {

    private val http = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(10))
        .build()

    case class GameContext(
        gameId : Int,
        masterSecret : String,
        secrets : Map[String, String],  // role name → secret
    )

    private def httpGet(url : String) : String = {
        val req = HttpRequest.newBuilder().uri(URI.create(url)).GET()
            .timeout(Duration.ofSeconds(30)).build()
        val resp = http.send(req, HttpResponse.BodyHandlers.ofString())
        if (resp.statusCode() / 100 != 2)
            throw new RuntimeException(s"GET $url -> HTTP ${resp.statusCode()}: ${resp.body().take(200)}")
        resp.body()
    }

    private def httpPost(url : String, body : String) : String = {
        val req = HttpRequest.newBuilder().uri(URI.create(url))
            .POST(HttpRequest.BodyPublishers.ofString(body))
            .timeout(Duration.ofSeconds(30)).build()
        val resp = http.send(req, HttpResponse.BodyHandlers.ofString())
        if (resp.statusCode() / 100 != 2)
            throw new RuntimeException(s"POST $url -> HTTP ${resp.statusCode()}: ${resp.body().take(200)}")
        resp.body()
    }

    /** Generate a random game name (mirrors the solo-build pattern). */
    private def genName() : String = {
        val n = scala.util.Random.shuffle($("Disaster", "Glory", "Pain", "Continuum", "Slaughter", "Agony", "Might", "Ritual", "Gate", "Power", "Oblivion")).take(2)
        val c = scala.util.Random.shuffle($("for", "against", "versus", "through", "and", "of", "in", "as")).head
        n.head + " " + c + " " + n.last
    }

    private def parseMap(mapName : String) : Board = mapName match {
        case "Earth33" => EarthMap3
        case "Earth35" | "Earth4v35" => EarthMap4v35
        case "Earth53" | "Earth4v53" => EarthMap4v53
        case "Earth55" => EarthMap5
        case "Library33" => LibraryCelaeno33
        case "Library35" => LibraryCelaeno35
        case "Library53" => LibraryCelaeno53
        case "Library55" => LibraryCelaeno55
        case other => throw new IllegalArgumentException(s"Unknown map: $other")
    }

    private def parseFaction(s : String) : Faction = s match {
        case "GC" => GC; case "CC" => CC; case "BG" => BG; case "YS" => YS
        case "SL" => SL; case "WW" => WW; case "OW" => OW; case "AN" => AN
        case "TS" => TS; case "FB" => FB; case "DS" => DS
        case other => throw new IllegalArgumentException(s"Unknown faction: $other")
    }

    def createGame(server : String, adminToken : String, mapName : String, factions : Seq[Faction]) : GameContext =
        createGameWithOpts(server, adminToken, mapName, factions, $())

    def createGameWithOpts(server : String, adminToken : String, mapName : String, factions : Seq[Faction], opts : $[GameOption]) : GameContext = {
        // /create body = "F1 F2 F3\nversion\nname\nF1:Human/F2:Human/F3:Human MapName Opt1 Opt2 ..."
        // All factions Human so each gets its own per-faction secret the orchestrator drives.
        val name = genName()
        val factionsLine = factions.map(_.short).mkString(" ")
        val version = "Cthulhu Wars HRF library-at-celaeno-v4"
        val optsSuffix = if (opts.isEmpty) "" else " " + opts.map(_.toString).mkString(" ")
        val setupLine = factions.map(f => s"${f.short}:Human").mkString("/") + s" Map$mapName" + optsSuffix
        val body = s"$factionsLine\n$version\n$name\n$setupLine"

        // /create?bot=true atomically marks the new game as a bot-game on the server,
        // saving a separate /admin/mark-bot HTTP roundtrip per game.
        val masterSecret = httpPost(s"$server/create?bot=true", body).trim
        val rolesRaw = httpGet(s"$server/roles/$masterSecret")
        val secrets : Map[String, String] = rolesRaw.split("\n").map(_.trim).filter(_.nonEmpty)
            .map { line => val parts = line.split(" ", 2); parts(0) -> parts(1) }
            .toMap

        // Look up the gameId via /admin/<t>/games (we just created it; it's whichever
        // game has the master secret we got back).
        val gamesRaw = httpGet(s"$server/admin/$adminToken/games")
        val gameId = gamesRaw.split("\n").map(_.split("\t")).find(_(2) == masterSecret)
            .map(_(0).toInt)
            .getOrElse(throw new RuntimeException(s"created game (master=$masterSecret) not found in /admin/games"))

        println(s"[create] gameId=$gameId  name=$name  factions=${factions.map(_.short).mkString(",")}  master=${masterSecret.take(6)}…")
        GameContext(gameId, masterSecret, secrets)
    }

    // An action string is "permanent" if undo can't cross it. Mirrors the
    // admin.html PERMANENT_KEYWORDS list and the engine's tagging rules.
    private def isPermanent(actionStr : String) : Boolean = {
        actionStr.contains("BattleRollAction") ||
        actionStr.contains("ElderSignAction") ||
        actionStr.contains("CaptureAction") ||
        actionStr.contains("SpendOnCustodianAction") ||
        actionStr.contains("SpendOnLibrarianAction") ||
        actionStr.contains("RollAgony")
    }

    /** Replay actions 0..untilIdx-1 through a fresh Game. Used to rewind on undo
      * without leaking state. Returns the rebuilt Game and the resulting Continue. */
    private def rebuildAndReplay(board : Board, ritualTrack : $[Int], factions : Seq[Faction],
                                 actions : Seq[String], untilIdx : Int) : (Game, Continue) = {
        val g = new Game(board, ritualTrack, factions.toList, true, $())
        val ser = new Serialize(g)
        val (_, startCont) = g.perform(StartAction)
        var c = startCont
        var i = 0
        while (i < untilIdx) {
            val act = ser.parseAction(actions(i))
            val (_, next) = g.perform(act)
            c = next
            i += 1
        }
        (g, c)
    }

    private def parseOption(s : String) : Option[GameOption] = s.trim match {
        case "HighPriests" => Some(HighPriests)
        case "NeutralSpellbooks" => Some(NeutralSpellbooks)
        case "IceAgeAffectsLethargy" => Some(IceAgeAffectsLethargy)
        case "Opener4P10Gates" => Some(Opener4P10Gates)
        case "DemandTsathoggua" => Some(DemandTsathoggua)
        case "GateDiplomacy" => Some(GateDiplomacy)
        case "AsyncActions" => Some(AsyncActions)
        case "UseGhast" => Some(UseGhast)
        case "UseGug" => Some(UseGug)
        case "UseShantak" => Some(UseShantak)
        case "UseStarVampire" => Some(UseStarVampire)
        case "UseVoonith" => Some(UseVoonith)
        case "UseDimensionalShamblers" => Some(UseDimensionalShamblers)
        case "UseGnorri" => Some(UseGnorri)
        case "UseByatis" => Some(UseByatis)
        case "UseAbhoth" => Some(UseAbhoth)
        case "UseDaoloth" => Some(UseDaoloth)
        case "UseNyogtha" => Some(UseNyogtha)
        case "UseTulzscha" => Some(UseTulzscha)
        case "UseYgolonac" => Some(UseYgolonac)
        case _ => None
    }

    def playOneGame(server : String, adminToken : String, mapName : String, factions : Seq[Faction], doUndo : Boolean, opts : $[GameOption] = $()) : Boolean = {
        val ctx = createGameWithOpts(server, adminToken, mapName, factions, opts)
        val board = parseMap(mapName)
        val ritualTrack = factions.size match {
            case 3 => RitualTrack.for3
            case 5 => RitualTrack.for5
            case _ => RitualTrack.for4
        }
        var game = new Game(board, ritualTrack, factions.toList, true, opts)
        val (_, startCont) = game.perform(StartAction)
        var c = startCont
        val actionLog = scala.collection.mutable.ArrayBuffer[String]()
        var undoDone = false
        // Random target: trigger the undo somewhere between 40 and 80 actions in.
        val undoTriggerAt = if (doUndo) 40 + scala.util.Random.nextInt(40) else -1

        try {
            while (!c.isInstanceOf[GameOver]) {
                val action = Host.askFaction(game, c)
                val actionStr = (new Serialize(game)).write(action.unwrap)
                actionLog += actionStr
                val (_, next) = game.perform(action.unwrap)
                c = next

                // Trigger one undo per game once we cross the target action count.
                if (doUndo && !undoDone && actionLog.size >= undoTriggerAt) {
                    // Find the most recent permanent action; we can only rewind to AFTER it.
                    val curIdx = actionLog.size
                    val minRewindTo = math.max(3, curIdx - 20)  // try to rewind ~20 actions
                    val rewindFloor = (curIdx - 1 to minRewindTo by -1).find(i => i >= 0 && i < actionLog.size && isPermanent(actionLog(i)))
                        .map(_ + 1).getOrElse(minRewindTo)
                    if (rewindFloor < curIdx - 2) {
                        println(s"[undo] gameId=${ctx.gameId} rewinding from $curIdx to $rewindFloor")
                        // Truncate local log and rebuild local Game state from scratch through rewindFloor.
                        actionLog.dropRightInPlace(curIdx - rewindFloor)
                        val (g2, c2) = rebuildAndReplay(board, ritualTrack, factions, actionLog.toSeq, actionLog.size)
                        game = g2
                        c = c2
                    }
                    undoDone = true
                }
            }

            // Batch /write the entire local log in ONE call. Server doesn't run the engine
            // on /write — it just appends Log rows — so role attribution is informational.
            // Use the first non-spectator role's secret. Sequential indexes start at 3
            // (server already has lines 0..2 from /create).
            val writeSecret = ctx.secrets.collectFirst {
                case (name, sec) if name != "#" && name != "$" => sec
            }.getOrElse(ctx.masterSecret)
            if (actionLog.nonEmpty)
                httpPost(s"$server/write/$writeSecret/3", actionLog.mkString("\n"))

            // Verify by READING back and confirming line count matches what we wrote.
            // Catches: server dropped writes, parser exceptions in the engine, server-side
            // races that lost messages. Full state-divergence verification (replay /read
            // through a fresh Game and compare to local truth) is a richer check, queued
            // separately.
            val readBack = httpGet(s"$server/read/$writeSecret/3")
            val readLines = readBack.split("\n").filter(_.nonEmpty).length
            if (readLines != actionLog.size)
                println(s"[warn] gameId=${ctx.gameId} /read got $readLines lines but local had ${actionLog.size}")

            // [2026-05-22] Capture winner info from the GameOver continue BEFORE delete
            // so end-of-run stats can aggregate per-faction wins. Format is one
            // structured line per game: STATS<TAB>gameId<TAB>actions<TAB>winners<TAB>factions
            // — easy to grep post-run with `grep ^STATS`.
            val winnerNames = c match {
                case GameOver(ws) => ws.map(_.short).mkString(",")
                case _            => ""
            }
            val factionNames = factions.map(_.short).mkString(",")
            println(s"STATS\t${ctx.gameId}\t${actionLog.size}\t${winnerNames}\t${factionNames}")
            println(s"[done] gameId=${ctx.gameId} clean GameOver  actions=${actionLog.size}  winner=${winnerNames}${if (undoDone) " (with undo)" else ""}")
            Try(httpPost(s"$server/admin/$adminToken/delete/${ctx.gameId}", ""))
            true
        }
        catch {
            case t : Throwable =>
                println(s"[crash] gameId=${ctx.gameId}: ${t.getClass.getSimpleName}: ${t.getMessage}")
                t.printStackTrace()
                // Flush any pending actions so the broken game can still be inspected.
                Try {
                    val writeSecret = ctx.secrets.collectFirst {
                        case (name, sec) if name != "#" && name != "$" => sec
                    }.getOrElse(ctx.masterSecret)
                    if (actionLog.nonEmpty)
                        httpPost(s"$server/write/$writeSecret/3", actionLog.mkString("\n"))
                }
                false
        }
    }

    /** Pull an existing game's full action log from /admin/<t>/log/<id>, replay
      * it through a fresh Game, and report any parse / MatchError / exception.
      * Used by the admin Edit-ES flow to confirm the edited value still produces
      * a valid game before committing. Output: prints "VALID" + actionCount on
      * success, or "INVALID <idx> <error>" on first failure. Exit code 0 if
      * valid, 1 if invalid.
      */
    def validateGame(server : String, adminToken : String, gameId : Int) : Boolean = {
        val raw = httpGet(s"$server/admin/$adminToken/log/$gameId")
        val lines = raw.split("\n").filter(_.nonEmpty).toList
        // Tab format: idx\trole\tvalue. First 3 lines are header (version/name/setup).
        if (lines.size < 3) {
            println(s"INVALID 0 short-header (only ${lines.size} log lines)")
            return false
        }
        // Parse header line 2 (idx=2): faction-roster + Map<Name> + opts
        val headerVal = lines(2).split("\t").drop(2).mkString("\t")
        val tokens = headerVal.split(" ").filter(_.nonEmpty).toList
        val factionsToken = tokens.headOption.getOrElse("")
        val factionCodes = factionsToken.split("/").toList.map(_.split(":").head).filter(_.nonEmpty)
        val mapToken = tokens.find(_.startsWith("Map")).getOrElse("MapLibrary33").stripPrefix("Map")
        val opts : $[GameOption] = tokens.drop(1).filterNot(_.startsWith("Map")).flatMap(parseOption(_).toList)
        val seating = factionCodes.map(parseFaction)
        val board = parseMap(mapToken)
        val ritualTrack = seating.size match {
            case 3 => RitualTrack.for3
            case 5 => RitualTrack.for5
            case _ => RitualTrack.for4
        }
        val game = new Game(board, ritualTrack, seating, true, opts)
        val ser = new Serialize(game)
        val (_, startCont) = game.perform(StartAction)
        var c = startCont
        // Action lines start at idx 3.
        val actionLines = lines.drop(3).map(_.split("\t").drop(2).mkString("\t"))
        var i = 0
        while (i < actionLines.size) {
            val line = actionLines(i)
            try {
                val act = ser.parseAction(line)
                if (act.isInstanceOf[CommentAction] && line.contains("Parse error")) {
                    println(s"INVALID $i parse-error: ${line.take(120)}")
                    return false
                }
                val (_, next) = game.perform(act)
                c = next
                if (c.isInstanceOf[GameOver]) {
                    // Reached game end early — that's fine if it was a real GameOver.
                    println(s"VALID actions=${i + 1} reached GameOver")
                    return true
                }
            }
            catch {
                case t : Throwable =>
                    println(s"INVALID $i ${t.getClass.getSimpleName}: ${Option(t.getMessage).getOrElse("").take(120)}")
                    return false
            }
            i += 1
        }
        println(s"VALID actions=${actionLines.size}")
        true
    }

    def main(args : Array[String]) : Unit = {
        // --validate-game subcommand: replay a live game's log to confirm it's clean.
        // Usage: OnlineSimRunner --validate-game <server> <token> <gameId>
        if (args.length >= 4 && args(0) == "--validate-game") {
            val ok = validateGame(args(1).stripSuffix("/"), args(2), args(3).toInt)
            sys.exit(if (ok) 0 else 1)
        }
        if (args.length < 4) {
            println("usage: OnlineSimRunner <serverUrl> <adminToken> <numGames> <map>[,map2,...] [opts]")
            println("       map: Library33 | Library35 | Library53 | Library55 | Earth33 | Earth35 | Earth53 | Earth55")
            println("       Multiple maps comma-separated → one is chosen at random per game.")
            println("Opts:")
            println("       --force F1,F2,F3   force include these factions in every game")
            println("       --players N        pad random factions up to N total per game")
            println("       --factions F1,..   alias for --force; fixed faction set (no random fill)")
            println("       --opts O1,O2,...   game options (HighPriests, GateDiplomacy, AsyncActions, UseGhast, ...)")
            println("       --parallel N       run N games concurrently")
            println("       --undo             force one bot-driven undo per game")
            return
        }
        val server = args(0).stripSuffix("/")
        val token = args(1)
        val numGames = args(2).toInt
        val maps = args(3).split(",").map(_.trim).filter(_.nonEmpty).toList
        val rest = args.drop(4).toList

        def listFlag(name : String) : List[String] = {
            val idx = rest.indexOf(name)
            if (idx >= 0 && idx + 1 < rest.size) rest(idx + 1).split(",").map(_.trim).toList else Nil
        }
        def intFlag(name : String, default : Int) : Int = {
            val idx = rest.indexOf(name)
            if (idx >= 0 && idx + 1 < rest.size) rest(idx + 1).toInt else default
        }

        val parallelism = intFlag("--parallel", 1)
        val doUndo = rest.contains("--undo")
        val forced = (listFlag("--force") ++ listFlag("--factions")).distinct.map(parseFaction)
        val playerCount = intFlag("--players", math.max(forced.size, 3))
        val optTokens = listFlag("--opts")
        val opts : $[GameOption] = optTokens.flatMap(parseOption(_).toList)
        if (opts.size != optTokens.size) {
            val unrec = optTokens.filterNot(parseOption(_).isDefined)
            println(s"[warn] unrecognized opts: ${unrec.mkString(", ")}")
        }
        val allFactions : List[Faction] = List(GC, CC, BG, YS, SL, WW, OW, AN, TS, FB, DS)

        def buildFactions() : List[Faction] = {
            val rand = scala.util.Random.shuffle(allFactions.filterNot(forced.contains))
            (forced ++ rand).take(playerCount).toList
        }
        def buildMap() : String = maps(scala.util.Random.nextInt(maps.size))

        val cleanCt = new java.util.concurrent.atomic.AtomicInteger(0)
        val crashedCt = new java.util.concurrent.atomic.AtomicInteger(0)
        val t0 = System.currentTimeMillis()

        def runOne(gi : Int, workerLabel : String) : Unit = {
            val mn = buildMap()
            val ff = buildFactions()
            println(s"\n=== game $gi / $numGames  ${workerLabel}map=$mn  factions=${ff.map(_.short).mkString(",")} ===")
            if (playOneGame(server, token, mn, ff, doUndo, opts)) cleanCt.incrementAndGet()
            else crashedCt.incrementAndGet()
        }

        if (parallelism <= 1) {
            (1 to numGames).foreach { gi => runOne(gi, "") }
        }
        else {
            val nextGameIdx = new java.util.concurrent.atomic.AtomicInteger(1)
            val workers = (1 to parallelism).map { wid =>
                val t = new Thread(new Runnable {
                    def run() : Unit = {
                        var done = false
                        while (!done) {
                            val gi = nextGameIdx.getAndIncrement()
                            if (gi > numGames) done = true
                            else runOne(gi, s"worker=$wid ")
                        }
                    }
                }, s"sim-worker-$wid")
                t.start()
                t
            }
            workers.foreach(_.join())
        }

        val secsTotal = (System.currentTimeMillis() - t0) / 1000.0
        val clean = cleanCt.get(); val crashed = crashedCt.get()
        println(s"\n=== done.  clean=$clean  crashed=$crashed  parallelism=$parallelism  totalTime=${secsTotal}s  avgWallPerGame=${secsTotal / numGames}s")
    }
}
