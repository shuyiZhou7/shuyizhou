import AVFoundation
import Foundation

struct ChatMessage: Identifiable {
    enum Role { case user, assistant, error }
    let id = UUID()
    let role: Role
    let text: String
}

@MainActor
final class ChatViewModel: ObservableObject {
    @Published private(set) var messages: [ChatMessage] = []
    @Published private(set) var isLoading = false

    @Published var apiKey: String {
        didSet { KeychainHelper.save(apiKey) }
    }
    @Published var model: String {
        didSet { UserDefaults.standard.set(model, forKey: "model") }
    }
    @Published var speakReplies: Bool {
        didSet { UserDefaults.standard.set(speakReplies, forKey: "speakReplies") }
    }

    /// 发给 API 的历史记录。assistant 回合保存完整 content（含 thinking 块），只追加不修改。
    private var history: [[String: Any]] = []
    private let speech = AVSpeechSynthesizer()

    init() {
        apiKey = KeychainHelper.load() ?? Config.defaultAPIKey
        model = UserDefaults.standard.string(forKey: "model") ?? Config.defaultModel
        speakReplies = UserDefaults.standard.bool(forKey: "speakReplies")
    }

    func send(_ raw: String) {
        let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isLoading else { return }

        messages.append(ChatMessage(role: .user, text: text))
        history.append(["role": "user", "content": text])
        isLoading = true

        let client = ClaudeClient(apiKey: apiKey, model: model)
        let snapshot = history
        Task {
            defer { isLoading = false }
            do {
                let reply = try await client.send(messages: snapshot)
                if reply.refused {
                    // 不把被拒绝的回合留在历史里，保证后续对话还能继续
                    history.removeLast()
                    messages.append(ChatMessage(role: .error, text: reply.text))
                } else {
                    history.append(["role": "assistant", "content": reply.content])
                    messages.append(ChatMessage(role: .assistant, text: reply.text))
                    if speakReplies { speak(reply.text) }
                }
            } catch {
                history.removeLast()
                messages.append(ChatMessage(role: .error, text: error.localizedDescription))
            }
        }
    }

    func reset() {
        guard !isLoading else { return }
        speech.stopSpeaking(at: .immediate)
        messages.removeAll()
        history.removeAll()
    }

    private func speak(_ text: String) {
        speech.stopSpeaking(at: .immediate)
        speech.speak(AVSpeechUtterance(string: text))
    }
}
