import Foundation
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let out = URL(fileURLWithPath: CommandLine.arguments[2])
let fm = FileManager.default
var ok = 0, bad = 0
let en = fm.enumerator(at: root, includingPropertiesForKeys: [.isDirectoryKey])!
for case let u as URL in en {
  if (try? u.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true { continue }
  let rel = String(u.path.dropFirst(root.path.count + 1))
  let dst = out.appendingPathComponent(rel)
  try? fm.createDirectory(at: dst.deletingLastPathComponent(), withIntermediateDirectories: true)
  try? fm.removeItem(at: dst)
  var e: NSError?
  var copied = false
  NSFileCoordinator().coordinate(readingItemAt: u, options: [.forUploading], error: &e) { src in
    if (try? fm.copyItem(at: src, to: dst)) != nil { copied = true }
  }
  if copied { ok += 1 } else { bad += 1; print("FAIL \(rel) \(e?.localizedDescription ?? "")") }
}
print("ok=\(ok) fail=\(bad)")
