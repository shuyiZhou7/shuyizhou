import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var chat: ChatViewModel

    var body: some View {
        Form {
            Section("API Key") {
                SecureField("sk-ant-…", text: $chat.apiKey)
            }
            Section("模型") {
                Picker("模型", selection: $chat.model) {
                    ForEach(Config.models, id: \.id) { option in
                        Text(option.name).tag(option.id)
                    }
                }
            }
            Toggle("朗读回复", isOn: $chat.speakReplies)
        }
    }
}
