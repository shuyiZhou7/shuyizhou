import Foundation

/// 直接调用 Claude Messages API（Swift 没有官方 SDK，所以用原生 HTTP）。
struct ClaudeClient {
    struct Reply {
        /// 完整的 assistant content 数组，需原样放回历史（包括 thinking 块）。
        let content: [[String: Any]]
        let text: String
        let refused: Bool
    }

    enum ClientError: LocalizedError {
        case missingKey
        case http(Int, String)
        case badResponse

        var errorDescription: String? {
            switch self {
            case .missingKey: return "请先在设置里填入 API Key"
            case .http(let code, let msg): return "错误 \(code)：\(msg)"
            case .badResponse: return "无法解析回复"
            }
        }
    }

    let apiKey: String
    let model: String

    func send(messages: [[String: Any]]) async throws -> Reply {
        guard !apiKey.isEmpty else { throw ClientError.missingKey }

        var body: [String: Any] = [
            "model": model,
            "max_tokens": 8000,
            "system": Config.systemPrompt,
            "messages": messages,
            // 手表聊天追求速度：低 effort 回复更快
            "output_config": ["effort": "low"],
        ]

        var request = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2026-10-21", forHTTPHeaderField: "anthropic-version")

        // Haiku 5.5 不支持服务端回退；其它模型被安全分类器拒绝时自动换模型重试
        if model != "claude-haiku-5-5" {
            request.setValue("server-side-fallback-2026-07-01", forHTTPHeaderField: "anthropic-beta")
            body["fallbacks"] = "default"
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw ClientError.badResponse
        }
        guard status == 200 else {
            let message = (json["error"] as? [String: Any])?["message"] as? String ?? "未知错误"
            throw ClientError.http(status, message)
        }
        guard let content = json["content"] as? [[String: Any]] else {
            throw ClientError.badResponse
        }

        if json["stop_reason"] as? String == "refusal" {
            return Reply(content: content, text: "Claude 无法回答这个问题。", refused: true)
        }

        let text = content
            .filter { $0["type"] as? String == "text" }
            .compactMap { $0["text"] as? String }
            .joined()
        return Reply(content: content, text: text, refused: false)
    }
}
