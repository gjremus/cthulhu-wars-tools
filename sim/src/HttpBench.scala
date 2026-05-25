package cws

import java.net.URI
import java.net.http.{HttpClient, HttpRequest, HttpResponse}
import java.time.Duration

/** Quick 100-request benchmark to find why localhost:8080 was 7× slower than
 * the cwo.freeddns.org loopback path in OnlineSimRunner. Measures wall-clock
 * for 100 sequential GETs to each URL, prints min/avg/p95/max. Helps determine
 * whether the problem is TCP setup, TLS handshake, akka-http per-call cost,
 * or Java HttpClient connection-pool behavior.
 *
 * Usage:
 *   java -cp <jar> cws.HttpBench <url1> [url2] [N]
 * Example on VM:
 *   java -cp /opt/cwo/server/online-sim.jar cws.HttpBench \
 *        https://cwo.freeddns.org/admin/<token>/games \
 *        http://localhost:8080/admin/<token>/games \
 *        100
 */
object HttpBench {
    def main(args : Array[String]) : Unit = {
        val urls = args.takeWhile(a => !a.matches("\\d+"))
        val n = args.find(_.matches("\\d+")).map(_.toInt).getOrElse(100)

        // Single HttpClient reused across requests — same pattern as OnlineSimRunner.
        val client = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build()

        urls.foreach { url =>
            println(s"\n=== $url  (n=$n) ===")
            val times = (1 to n).map { i =>
                val req = HttpRequest.newBuilder().uri(URI.create(url)).GET()
                    .timeout(Duration.ofSeconds(30)).build()
                val t0 = System.nanoTime()
                val resp = client.send(req, HttpResponse.BodyHandlers.ofString())
                val dtMs = (System.nanoTime() - t0) / 1_000_000.0
                if (i <= 3 || i % 20 == 0)
                    println(f"  req $i%3d: ${dtMs}%6.1f ms  status=${resp.statusCode()}  bytes=${resp.body().length()}")
                dtMs
            }
            val sorted = times.sorted
            val avg = times.sum / times.size
            val min = sorted.head
            val max = sorted.last
            val p95 = sorted((times.size * 0.95).toInt)
            println(f"  -- summary: min=${min}%5.1f  avg=${avg}%5.1f  p95=${p95}%5.1f  max=${max}%6.1f ms")
        }
    }
}
