import Foundation

struct Word: Codable, Identifiable, Hashable {
    let word: String
    let phonetic: String
    let meaning: String
    let example: String
    let exampleZh: String

    var id: String { word }
}

enum WordBank {
    /// 读取打包在 App 里的 Words.json
    static func load() -> [Word] {
        guard let url = Bundle.main.url(forResource: "Words", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let words = try? JSONDecoder().decode([Word].self, from: data) else {
            return []
        }
        return words
    }
}
