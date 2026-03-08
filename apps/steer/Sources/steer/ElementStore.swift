import Foundation

enum ElementStore {
    private static var cache: [String: [UIElement]] = [:]
    static let dir = FileManager.default.temporaryDirectory.appendingPathComponent("steer")

    static func save(id: String, elements: [UIElement]) {
        cache[id] = elements
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let enc = JSONEncoder()
        enc.outputFormatting = .prettyPrinted
        if let d = try? enc.encode(elements) {
            try? d.write(to: dir.appendingPathComponent("\(id).json"))
        }
    }

    static func load(id: String) -> [UIElement]? {
        if let c = cache[id] { return c }
        guard let d = try? Data(contentsOf: dir.appendingPathComponent("\(id).json")) else { return nil }
        let els = try? JSONDecoder().decode([UIElement].self, from: d)
        if let els = els { cache[id] = els }
        return els
    }

    static func latest() -> (String, [UIElement])? {
        // Check in-memory cache first
        if let l = cache.max(by: { $0.key < $1.key }) { return (l.key, l.value) }
        // Fall back to disk
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: [.contentModificationDateKey]) else { return nil }
        let sorted = files
            .filter { $0.pathExtension == "json" }
            .sorted { a, b in
                let da = (try? a.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
                let db = (try? b.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? .distantPast
                return da > db
            }
        guard let newest = sorted.first,
              let data = try? Data(contentsOf: newest),
              let els = try? JSONDecoder().decode([UIElement].self, from: data) else { return nil }
        let id = newest.deletingPathExtension().lastPathComponent
        cache[id] = els
        return (id, els)
    }

    static func resolve(_ q: String, snap: String? = nil) throws -> UIElement {
        let els: [UIElement]
        if let s = snap, let e = load(id: s) { els = e }
        else if let l = latest() { els = l.1 }
        else { throw SteerError.noSnapshot }

        let lq = q.lowercased()
        // Exact ID match: B1, T2, S3
        if let e = els.first(where: { $0.id.lowercased() == lq }) { return e }
        // Exact label match
        if let e = els.first(where: { $0.label.lowercased() == lq }) { return e }
        // Partial label match
        if let e = els.first(where: { $0.label.lowercased().contains(lq) }) { return e }

        throw SteerError.elementNotFound(q)
    }
}
