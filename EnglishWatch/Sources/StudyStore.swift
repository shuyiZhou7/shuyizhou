import Foundation

enum Rating {
    case again, good, easy
}

/// 每个单词的记忆状态（莱特纳盒子法）：盒子越高，下次复习间隔越长
struct CardState: Codable {
    var box = 0
    var due = Date.distantPast
    var reviews = 0
    var lapses = 0
}

struct QuizQuestion {
    let word: Word
    let options: [String]
    let answer: Int
}

@MainActor
final class StudyStore: ObservableObject {
    /// 各盒子对应的复习间隔（天）
    static let intervalDays: [Double] = [0, 1, 2, 4, 7, 15, 30, 60]

    let words: [Word]
    @Published private(set) var states: [String: CardState] = [:]
    @Published private var newToday = 0
    @Published private var reviewedToday = 0
    @Published private var streak = 0
    @Published var dailyNewLimit = 10 { didSet { save() } }
    @Published var autoSpeak = true { didSet { save() } }

    private var statsDay = ""
    private var lastStudyDay = ""
    private let storageKey = "EnglishWatch.progress"

    private struct SaveData: Codable {
        var states: [String: CardState]
        var newToday: Int
        var reviewedToday: Int
        var statsDay: String
        var streak: Int
        var lastStudyDay: String
        var dailyNewLimit: Int
        var autoSpeak: Bool
    }

    init(words: [Word] = WordBank.load()) {
        self.words = words
        load()
    }

    // MARK: - 统计

    var newTodayCount: Int { statsDay == todayString ? newToday : 0 }
    var reviewedTodayCount: Int { statsDay == todayString ? reviewedToday : 0 }
    var currentStreak: Int {
        lastStudyDay == todayString || lastStudyDay == yesterdayString ? streak : 0
    }
    var learnedCount: Int { states.values.filter { $0.box >= 1 }.count }
    var masteredCount: Int { states.values.filter { $0.box >= 5 }.count }
    var dueCount: Int {
        let now = Date()
        return states.values.filter { $0.due <= now }.count
    }
    var newRemaining: Int {
        let unseen = words.count - states.count
        return max(0, min(dailyNewLimit - newTodayCount, unseen))
    }

    // MARK: - 学习

    /// 今天的学习队列：先复习到期的单词，再学新词
    func makeSession() -> [Word] {
        rollDay()
        let now = Date()
        let due = words
            .filter { (states[$0.id]?.due ?? .distantFuture) <= now }
            .sorted { (states[$0.id]?.due ?? now) < (states[$1.id]?.due ?? now) }
        let fresh = words.filter { states[$0.id] == nil }.prefix(newRemaining)
        return due + fresh
    }

    func grade(_ word: Word, _ rating: Rating) {
        rollDay()
        let isNew = states[word.id] == nil
        var s = states[word.id] ?? CardState()
        switch rating {
        case .again:
            if s.box > 0 { s.lapses += 1 }
            s.box = 0
            s.due = Date().addingTimeInterval(60)
        case .good, .easy:
            s.box = min(s.box + (rating == .easy ? 2 : 1), Self.intervalDays.count - 1)
            s.due = Date().addingTimeInterval(Self.intervalDays[s.box] * 86_400)
        }
        s.reviews += 1
        states[word.id] = s
        if isNew { newToday += 1 } else { reviewedToday += 1 }
        touchStreak()
        save()
    }

    // MARK: - 测验

    /// 看英文选中文；优先从学过的单词里出题
    func makeQuiz() -> QuizQuestion? {
        guard words.count >= 4 else { return nil }
        let learned = words.filter { states[$0.id] != nil }
        let pool = learned.count >= 1 ? learned : words
        guard let target = pool.randomElement() else { return nil }
        let distractors = words
            .filter { $0.id != target.id }
            .shuffled()
            .prefix(3)
            .map(\.meaning)
        let options = (distractors + [target.meaning]).shuffled()
        return QuizQuestion(word: target, options: options,
                            answer: options.firstIndex(of: target.meaning) ?? 0)
    }

    /// 测验答错的已学单词重新放回复习队列
    func recordQuiz(_ word: Word, correct: Bool) {
        if !correct && states[word.id] != nil {
            grade(word, .again)
        }
    }

    func resetProgress() {
        states = [:]
        newToday = 0
        reviewedToday = 0
        streak = 0
        lastStudyDay = ""
        save()
    }

    // MARK: - 日期与连续天数

    private static func dayString(_ date: Date) -> String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: date)
    }

    private var todayString: String { Self.dayString(Date()) }

    private var yesterdayString: String {
        Self.dayString(Calendar.current.date(byAdding: .day, value: -1, to: Date()) ?? Date())
    }

    private func rollDay() {
        if statsDay != todayString {
            statsDay = todayString
            newToday = 0
            reviewedToday = 0
        }
    }

    private func touchStreak() {
        let today = todayString
        guard lastStudyDay != today else { return }
        streak = lastStudyDay == yesterdayString ? streak + 1 : 1
        lastStudyDay = today
    }

    // MARK: - 保存

    private func save() {
        let data = SaveData(states: states, newToday: newToday, reviewedToday: reviewedToday,
                            statsDay: statsDay, streak: streak, lastStudyDay: lastStudyDay,
                            dailyNewLimit: dailyNewLimit, autoSpeak: autoSpeak)
        if let encoded = try? JSONEncoder().encode(data) {
            UserDefaults.standard.set(encoded, forKey: storageKey)
        }
    }

    private func load() {
        guard let raw = UserDefaults.standard.data(forKey: storageKey),
              let d = try? JSONDecoder().decode(SaveData.self, from: raw) else {
            return
        }
        states = d.states
        newToday = d.newToday
        reviewedToday = d.reviewedToday
        statsDay = d.statsDay
        streak = d.streak
        lastStudyDay = d.lastStudyDay
        dailyNewLimit = d.dailyNewLimit
        autoSpeak = d.autoSpeak
    }
}
