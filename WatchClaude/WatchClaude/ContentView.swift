import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var chat: ChatViewModel
    @State private var draft = ""
    @State private var showSettings = false

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 8) {
                        if chat.messages.isEmpty {
                            Text("点下面的输入框，用语音或手写和 Claude 聊天")
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                        ForEach(chat.messages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                        if chat.isLoading {
                            ProgressView().frame(maxWidth: .infinity)
                        }
                        TextField("说点什么…", text: $draft)
                            .disabled(chat.isLoading)
                            .onSubmit {
                                chat.send(draft)
                                draft = ""
                            }
                            .id("input")
                    }
                }
                .onChange(of: chat.messages.count) {
                    withAnimation { proxy.scrollTo("input", anchor: .bottom) }
                }
            }
            .navigationTitle("Claude")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { chat.reset() } label: { Image(systemName: "square.and.pencil") }
                        .disabled(chat.messages.isEmpty || chat.isLoading)
                }
            }
            .sheet(isPresented: $showSettings) {
                SettingsView()
            }
        }
    }
}

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        let isUser = message.role == .user
        Text(message.text)
            .font(.footnote)
            .padding(8)
            .background(background, in: RoundedRectangle(cornerRadius: 10))
            .frame(maxWidth: .infinity, alignment: isUser ? .trailing : .leading)
    }

    private var background: Color {
        switch message.role {
        case .user: return .orange.opacity(0.6)
        case .assistant: return .gray.opacity(0.3)
        case .error: return .red.opacity(0.4)
        }
    }
}
