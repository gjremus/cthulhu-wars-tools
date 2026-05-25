package cws

import hrf.colmat._

object ParseProbe {
    def main(args : Array[String]) : Unit = {
        val board = EarthMap4v35
        val ritualTrack = RitualTrack.for4
        val g = new Game(board, ritualTrack, $(GC, CC, BG, YS), false, $)
        val ser = new Serialize(g)
        val cases = $(
            "ThousandFormsAskAction(CC, 4, [FB->1], [TS, FB, DS], 8, DS, 0)",
            "ThousandFormsAskAction(CC, 4, [DS->0, FB->1], [FB, DS, TS], 7, TS, -1)",
            "ThousandFormsAskAction(CC, 4, [], [FB], 7, FB, 0)",
            "GhrothAskAction(BG, 3, [FB->1], [TS, FB], 5, FB, 0)"
        )
        cases.foreach { s =>
            val a = ser.parseAction(s)
            println("INPUT : " + s)
            println("PARSED: " + a.getClass.getSimpleName + " => " + a)
            println("WRITE : " + ser.write(a))
            println("-")
        }
    }
}
