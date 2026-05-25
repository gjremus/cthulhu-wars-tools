package cws

import hrf.colmat._

// ── ORPHAN: action-log replay tool ──────────────────────────────────────────
// Extracted from SimRunner per user direction 2026-05-22: SimRunner should
// only orchestrate NEW bot-vs-bot games against the live online server. The
// "load a previously-played action log and re-execute it locally" path is NOT
// what SimRunner is for. Kept here in case we ever need it again (e.g., to
// reproduce a customer-reported crash from a live game's persisted log).
//
// To invoke:
//   sbt "runMain cws.SimReplayOrphan --replay <input> [<output>] [--audit FACTION <csv-out>]"
//
// Input file format (header + action lines):
//   line 1: Cthulhu Wars 1.18 Replay
//   line 2: <FACTIONS> Map<MapName> PlayerCount(N) [opts...]
//   line 3+: action strings (one per line)
//
// Output file: action lines followed by HTML log divs.

object SimReplayOrphan {
    def main(args : Array[String]) : Unit = {
        if (args.length < 2 || args(0) != "--replay") {
            println("usage: SimReplayOrphan --replay <input> [<output>] [--audit FACTION <csv-out>]")
            return
        }
        val inputPath = args(1)
        val outputPath = if (args.length > 2 && !args(2).startsWith("--")) args(2) else inputPath.replace(".txt", "-log.txt")
        val lines = scala.io.Source.fromFile(inputPath).getLines().toList.map(_.trim).filter(_.nonEmpty)

        // Parse header: "Cthulhu Wars 1.18 Replay" then "BG-YS-SL-FB MapEarth35 PlayerCount(4)"
        val headerLine = lines.find(_.contains("Map")).getOrElse(lines(1))
        val factionCodes = headerLine.split(" ")(0).split("-").toList
        val mapName = headerLine.split(" ").find(_.startsWith("Map")).getOrElse("MapEarth35").replace("Map", "")
        val pcMatch = "PlayerCount\\((\\d+)\\)".r.findFirstMatchIn(headerLine)
        val pc = pcMatch.map(_.group(1).toInt).getOrElse(factionCodes.size)

        val board = mapName match {
            case "Earth33" => EarthMap3
            case "Earth35" | "Earth4v35" => EarthMap4v35
            case "Earth53" | "Earth4v53" => EarthMap4v53
            case "Earth55" => EarthMap5
            case "Library33" => LibraryCelaeno33
            case "Library35" => LibraryCelaeno35
            case "Library53" => LibraryCelaeno53
            case "Library55" => LibraryCelaeno55
            case _ => EarthMap4v35
        }
        val ritualTrack = pc match {
            case 3 => RitualTrack.for3
            case 5 => RitualTrack.for5
            case _ => RitualTrack.for4
        }

        var opts : $[GameOption] = $
        if (headerLine.contains("HighPriests")) opts :+= HighPriests
        if (headerLine.contains("UseGhast")) opts :+= UseGhast
        if (headerLine.contains("UseGug")) opts :+= UseGug
        if (headerLine.contains("UseShantak")) opts :+= UseShantak
        if (headerLine.contains("UseStarVampire")) opts :+= UseStarVampire
        if (headerLine.contains("UseVoonith")) opts :+= UseVoonith
        if (headerLine.contains("UseDimensionalShamblers")) opts :+= UseDimensionalShamblers
        if (headerLine.contains("UseGnorri")) opts :+= UseGnorri
        if (headerLine.contains("UseByatis")) opts :+= UseByatis
        if (headerLine.contains("UseAbhoth")) opts :+= UseAbhoth
        if (headerLine.contains("UseDaoloth")) opts :+= UseDaoloth
        if (headerLine.contains("UseNyogtha")) opts :+= UseNyogtha
        if (headerLine.contains("UseTulzscha")) opts :+= UseTulzscha
        if (headerLine.contains("UseYgolonac")) opts :+= UseYgolonac
        if (headerLine.contains("Opener4P10Gates")) opts :+= Opener4P10Gates

        def parseFactionReplay(s : String) : Faction = s match {
            case "GC" => GC; case "CC" => CC; case "BG" => BG; case "YS" => YS
            case "SL" => SL; case "WW" => WW; case "OW" => OW; case "AN" => AN
            case "TS" => TS; case "FB" => FB; case "DS" => DS
        }
        val seating = factionCodes.map(parseFactionReplay)
        val game = new Game(board, ritualTrack, seating, true, opts)
        val serializer = new Serialize(game)

        val actionLines = lines.filter(l =>
            !l.startsWith("Cthulhu Wars") && !l.contains("Map") && !l.startsWith("<div") &&
            !l.startsWith("Options") && l.nonEmpty)

        val auditIdx = args.indexOf("--audit")
        val auditFaction : Option[Faction] =
            if (auditIdx >= 0 && auditIdx + 1 < args.length) Some(parseFactionReplay(args(auditIdx + 1))) else None
        val auditCsvPath : Option[String] =
            if (auditIdx >= 0 && auditIdx + 2 < args.length) Some(args(auditIdx + 2)) else None
        auditFaction.foreach { f => Bot3.traceFaction = Some(f) }
        val auditRows = scala.collection.mutable.ListBuffer[String]()
        auditRows += "idx,turn,phase,ask_class,num_options,actual,bot_pick,matched,actual_w,top_w,runner_w,margin,top_reasons"

        var log : $[String] = $
        def writeLog(s : String) { log :+= s }

        println("Replaying " + actionLines.size + " actions for " + seating.map(_.short).mkString("-") + " on " + mapName + " (" + pc + "p)")
        auditFaction.foreach(f => println("Audit mode: scoring " + f.short + " decisions → " + auditCsvPath.getOrElse("(no path)")))

        val (startLog, startCont) = game.perform(StartAction)
        startLog.foreach(writeLog)
        var c = startCont
        var actionIdx = 0

        try {
            while (!c.isInstanceOf[GameOver] && actionIdx < actionLines.size) {
                val actionStr = actionLines(actionIdx).replace("&gt;", ">")
                try {
                    val action = serializer.parseAction(actionStr)
                    (auditFaction, c) match {
                        case (Some(af), ask : Ask) if ask.faction == af && ask.actions.num > 1 =>
                            val sn = action.unwrap.getClass.getSimpleName
                            val skip = sn.contains("EndTurn") || sn.contains("MoveDone") ||
                                sn == "MainAction" || sn == "MainGatesAction" || sn == "PreMainAction" ||
                                sn.contains("PassAction") || sn.contains("DoomDone") || sn.contains("NextPlayer")
                            if (!skip) {
                                try {
                                    val botPick = Host.askFaction(game, c)
                                    val evals = Bot3.lastEval
                                    def topAbs(ws : $[Int]) : Int =
                                        if (ws.isEmpty) 0 else ws.maxBy(_.abs)
                                    val actualEvalOpt = evals.find(_.action.unwrap == action.unwrap)
                                    val actualW = actualEvalOpt.map(ae => topAbs(ae.evaluations.map(_.weight))).getOrElse(0)
                                    val ranked = evals.sortBy(ae => -topAbs(ae.evaluations.map(_.weight)).abs)
                                    val topW = ranked.headOption.map(ae => topAbs(ae.evaluations.map(_.weight))).getOrElse(0)
                                    val runnerW = ranked.drop(1).headOption.map(ae => topAbs(ae.evaluations.map(_.weight))).getOrElse(0)
                                    val margin = topW - actualW
                                    val matched = botPick.unwrap == action.unwrap
                                    val reasons = actualEvalOpt.toList.flatMap(_.evaluations.filter(_.weight != 0)
                                        .sortBy(e => -e.weight.abs).take(3)
                                        .map(e => e.weight + ":" + e.desc.replaceAll("[,|\n]", ";").take(50))).mkString("|")
                                    def sanitize(s : String) : String = s.replaceAll("[,\n]", " ").take(80)
                                    val actualShort = sanitize(action.unwrap.toString)
                                    val pickShort = sanitize(botPick.unwrap.toString)
                                    val phase = if (game.battle.any) "battle" else "main"
                                    auditRows += s"$actionIdx,${game.turn},$phase,$sn,${ask.actions.num},$actualShort,$pickShort,$matched,$actualW,$topW,$runnerW,$margin,$reasons"
                                } catch { case _ : Throwable => }
                            }
                        case _ =>
                    }
                    val (ll, cc) = game.perform(action)
                    ll.foreach(writeLog)
                    c = cc
                } catch {
                    case e : Throwable =>
                        writeLog("<div class='p'>REPLAY ERROR at action " + actionIdx + ": " + actionStr.take(80) + " [" + e.getClass.getSimpleName + ": " + (if (e.getMessage != null) e.getMessage.take(60) else "null") + "]</div>")
                }
                actionIdx += 1
            }
        } catch {
            case _ : Throwable =>
                writeLog("<div class='p'>REPLAY ENDED at action " + actionIdx + "</div>")
        }

        val writer = new java.io.PrintWriter(new java.io.File(outputPath))
        actionLines.foreach(writer.println)
        writer.println()
        writer.println()
        log.foreach(s => writer.println("<div class='p'>" + s + "</div>"))
        writer.close()

        println("Written " + actionLines.size + " actions + " + log.size + " log lines to " + outputPath)

        auditCsvPath.foreach { p =>
            val w = new java.io.PrintWriter(new java.io.File(p))
            auditRows.foreach(w.println)
            w.close()
            println("Wrote " + (auditRows.size - 1) + " audit rows to " + p)
        }
    }
}
