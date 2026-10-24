# WatchClaude —— 在 Apple Watch 上和 Claude 聊天

一个独立的 watchOS 应用（不需要 iPhone 端 App）：用语音输入 / 手写 / 键盘发消息，Claude 回复会显示在手表上，也可以开启自动朗读。

## 你需要准备

- 一台装有 **Xcode 15 或更新版本**的 Mac
- Apple Watch 系统 **watchOS 10 或更新版本**
- 一个 Anthropic API Key：在 <https://console.anthropic.com> 创建（API 按用量计费，跟 Claude.ai 订阅是分开的）

## 安装步骤

1. 打开 Xcode → **File › New › Project…** → 选 **watchOS › App** → Next。
2. Product Name 填 `WatchClaude`，Interface 选 **SwiftUI**，勾选 **Watch-only App**，创建项目。
3. 删掉 Xcode 自动生成的 `ContentView.swift` 和 `WatchClaudeApp.swift`。
4. 把本文件夹 `WatchClaude/` 里的 7 个 `.swift` 文件拖进 Xcode 的 Watch App 目标里（勾选 "Copy items if needed"）。
5. （推荐）打开 `Config.swift`，把 API Key 填进 `defaultAPIKey`，免得在手表上打一长串字。**填好后不要提交到 GitHub。**
6. 在 **Signing & Capabilities** 里选你自己的 Apple ID 团队（免费账号也行，但 7 天后要重新安装）。
7. iPhone 和手表都开启**开发者模式**，顶部选你的手表作为运行设备，点 ▶ 运行。

## 怎么用

- 点输入框 → 说话（或手写），确认后就发给 Claude。
- 左上角 ⚙️：改 API Key、切换模型（Opus 5.5 / Sonnet 5.5 / Haiku 5.5）、开关**朗读回复**。
- 右上角 ✏️：开始新对话。
- 系统提示词要求 Claude 回答简短，适合手表屏幕；想改的话编辑 `Config.swift` 里的 `systemPrompt`。

手表连着 iPhone、Wi-Fi 或蜂窝网络都能用。

## 不想装 Xcode？用「快捷指令」5 分钟搞定

在 iPhone 的「快捷指令」App 里新建一个快捷指令：

1. **听写文本**（或「要求输入」）
2. **获取 URL 内容**：
   - URL：`https://api.anthropic.com/v1/messages`，方法 **POST**
   - 头部：`x-api-key` = 你的 Key；`anthropic-version` = `2026-10-21`；`content-type` = `application/json`
   - 请求体选 JSON：
     - `model`（文本）= `claude-opus-5-5`
     - `max_tokens`（数字）= `2000`
     - `messages`（数组）→ 一个字典：`role` = `user`，`content` = 第 1 步的「听写的文本」
3. **获取词典值**：键 `content`
4. **从列表中获取项目**：选 **最后一项**（Claude 的思考块排在前面，最后一项才是回答文字）
5. **获取词典值**：键 `text`
6. **显示结果**（或「朗读文本」）

在快捷指令的详情里打开 **在 Apple Watch 上显示**，然后就能在手表的快捷指令 App、表盘复杂功能或 Siri 里运行。缺点是每次只能单轮问答，不记得上下文——要多轮对话就用上面的 App。

## 安全提示

API Key 保存在手表的钥匙串里，只适合自己用。别把带 Key 的代码分享给别人；如果泄露了，去 Console 里删除这个 Key 重新生成。
