import Foundation

enum Config {
    /// 可选：在这里填入你的 Anthropic API Key，省去在手表上输入的麻烦。
    /// 千万不要把填好 Key 的这个文件提交到 GitHub！
    /// 也可以留空，然后在 App 的「设置」里输入（会存进钥匙串）。
    static let defaultAPIKey = ""

    static let models: [(id: String, name: String)] = [
        ("claude-opus-5-5", "Opus 5.5（最聪明）"),
        ("claude-sonnet-5-5", "Sonnet 5.5（均衡）"),
        ("claude-haiku-5-5", "Haiku 5.5（最快最省）"),
    ]
    static let defaultModel = "claude-opus-5-5"

    static let systemPrompt = """
    你正在 Apple Watch 上和用户聊天。屏幕很小，所以请简洁地回答：\
    通常 1~4 句话，除非用户明确要求详细说明。不要用 Markdown 表格、标题或代码块，\
    用纯文本。用用户使用的语言回答。
    """
}
