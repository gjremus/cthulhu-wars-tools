#!/usr/bin/env python3
"""Append the HB Fix 114 entry to the Homebrew Deployed Online Rollback Guide.docx,
matching the existing Heading1 / Heading2 + Body Text structure of prior fixes."""
import docx

PATH = "/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/HomeBrews/Homebrew Deployed Online Rollback Guide.docx"

d = docx.Document(PATH)

def h1(t): d.add_paragraph(t, style="Heading 1")
def h2(t): d.add_paragraph(t, style="Heading 2")
def body(t): d.add_paragraph(t, style="Body Text")

h1("Fix 114 (2026-06-13) — DC gate-build crash when Y’Golonac shares a region with a Cultist")

h2("Symptom.")
body("Building (or otherwise gaining control of) a Gate in a region that contained BOTH DC’s Y’Golonac AND a DC Cultist crashed the game. The replay reported: “scala.MatchError: Y’Golonac (of class cws.YgolonacDC$)  Action: BuildGateAction(DC, Asia…)”. The freeze happened the instant the gate was built/auto-controlled in such a region.")

h2("Root cause.")
body("checkGatesGained() in solo/Game.scala chooses which unit “marks” a newly controlled Gate by sorting the region’s gate-controlling units with a partial-function literal: self.at(r).%(_.canControlGate).sortBy(_.uclass @@ { case DarkYoung => 1; case Acolyte => 2; case HighPriest => 3 }). That partial function had NO default case. Normally only Cultists can control a Gate, so only those three cases were ever hit. But DC’s Y’Golonac overrides canControlGate to true (Bacchanal, §1.8 — “Y’Golonac can Build & Control Gates”), so when Y’Golonac and a Cultist share the region the GOO reaches the sort and the partial function throws scala.MatchError on YgolonacDC.")

h2("Fix.")
body("Added a default case _ => 4 to the sort partial function so any gate-controlling GOO is handled gracefully instead of crashing. A Cultist (priority 1–3) is still preferred as the Gate marker when one is present; Y’Golonac sorts last but no longer crashes, and can mark the Gate himself if he is the only eligible controller. Mirrors the already-defaulted GOO sort used elsewhere (solo/CthulhuWarsSolo.scala GC-deep render, case _ => 22).")

h2("Files changed.")
body("solo/Game.scala — checkGatesGained() gate-controller sort: added case _ => 4 default to the _.uclass @@ {…} partial function (HB Fix 114 comment in-line).")
body("solo/common.sbt — version bump Homebrew v 2.5 -> Homebrew v 2.6.")
body("NOT committed (pre-existing, in-progress, does NOT compile — left out of this build, same as Fix 113): an in-flight Faceless Blight (FBE) faction stub across solo/Game.scala + solo/Map.scala (references FBE / FBEExpansion that are not yet defined), solo/Battle.scala (FB Cyclopean Gaze post-battle snapshot), solo/CthulhuWarsSolo.scala (replay crash-handler), and an unrelated server-deploy/deploy-mnu-to-vm.sh edit. These were git-stashed before building so the shipped HB build contains ONLY the Fix 114 crash fix on top of Fix 113. Tasks 2 (DC Lure enemy-presence block) and 3 (DC Tenebrosum Summon/Awaken broaden) were already shipped in Fix 113 and were re-audited against the DC guide / owner directive — no further change needed.")

h2("Build + ship.")
body("cd /Users/gremus/Claude-Projects/cw-homebrew-wt/solo && sbt fullOptJS")
body("Closure: 0 error(s), 0 warning(s). Then ./server-deploy/deploy-homebrew-to-vm.sh . Cache tag 20260613-150755, public HTTP 200 at https://cwo.freeddns.org/HB/, shipped Homebrew v 2.6 (verified “Homebrew v 2.6” baked into the deployed main.js).")

h2("Git commit.")
body("e3a781f on branch homebrew (repo gjremus/cthulhu-wars). Message: “HB Fix 114: fix gate-build crash when Y’Golonac shares a region with a cultist (DC)”. Touches exactly solo/Game.scala and solo/common.sbt.")

h2("Rollback.")
body("git revert e3a781f (touches only solo/Game.scala and solo/common.sbt), rebuild Homebrew (sbt fullOptJS), redeploy. Restores Fix 113 behavior (Homebrew v 2.5) — i.e. the gate-build MatchError returns when Y’Golonac and a Cultist share a region during a gate build/control.")

d.save(PATH)
print("Appended Fix 114 entry. Total paragraphs:", len(d.paragraphs))
