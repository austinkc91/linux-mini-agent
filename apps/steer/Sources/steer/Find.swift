import ArgumentParser
import Foundation

struct Find: ParsableCommand {
    static let configuration = CommandConfiguration(
        abstract: "Search elements by text in the latest snapshot."
    )

    @Argument(help: "Text to search for (case-insensitive, partial match)")
    var query: String

    @Option(name: .long, help: "Snapshot ID to search in")
    var snapshot: String?

    @Flag(name: .long, help: "Exact match only")
    var exact = false

    @Flag(name: .long, help: "Output JSON")
    var json = false

    func run() throws {
        let els: [UIElement]
        let snapId: String

        if let s = snapshot, let e = ElementStore.load(id: s) {
            els = e; snapId = s
        } else if let l = ElementStore.latest() {
            els = l.1; snapId = l.0
        } else {
            throw SteerError.noSnapshot
        }

        let lq = query.lowercased()
        let matches: [UIElement]
        if exact {
            matches = els.filter { $0.label.lowercased() == lq || ($0.value?.lowercased() == lq) }
        } else {
            matches = els.filter { $0.label.lowercased().contains(lq) || ($0.value?.lowercased().contains(lq) ?? false) }
        }

        if json {
            let enc = JSONEncoder()
            enc.outputFormatting = [.prettyPrinted, .sortedKeys]
            let mJson = (try? String(data: enc.encode(matches), encoding: .utf8)) ?? "[]"
            print("{\"snapshot\":\"\(snapId)\",\"query\":\"\(query)\",\"count\":\(matches.count),\"matches\":\(mJson)}")
        } else {
            print("snapshot: \(snapId)")
            print("query: \"\(query)\"")
            print("matches: \(matches.count)")
            print("")
            if matches.isEmpty {
                print("  (no matches)")
            } else {
                for el in matches {
                    let lbl = el.label.isEmpty ? (el.value ?? "") : el.label
                    let t = String(lbl.prefix(50))
                    print("  \(el.id.padding(toLength: 6, withPad: " ", startingAt: 0)) \(el.role.padding(toLength: 14, withPad: " ", startingAt: 0)) \"\(t)\"  (\(el.x),\(el.y) \(el.width)x\(el.height))")
                }
            }
        }
    }
}
