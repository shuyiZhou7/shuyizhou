import SwiftUI

struct StudyView: View {
    @EnvironmentObject private var store: StudyStore
    @State private var queue: [Word] = []
    @State private var index = 0
    @State private var showBack = false
    @State private var started = false

    var body: some View {
        Group {
            if index < queue.count {
                card(queue[index])
            } else {
                VStack(spacing: 8) {
                    Text("🎉").font(.largeTitle)
                    Text(queue.isEmpty ? "今天没有要学的单词了" : "今天的任务完成了！")
                        .multilineTextAlignment(.center)
                    Text("连续学习 \(store.currentStreak) 天")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .navigationTitle(index < queue.count ? "\(index + 1)/\(queue.count)" : "完成")
        .onAppear {
            guard !started else { return }
            started = true
            queue = store.makeSession()
            speakCurrent()
        }
    }

    private func card(_ w: Word) -> some View {
        ScrollView {
            VStack(spacing: 6) {
                Text(w.word)
                    .font(.title2.bold())
                    .lineLimit(1)
                    .minimumScaleFactor(0.5)
                HStack(spacing: 6) {
                    Text(w.phonetic)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    Button {
                        Speaker.shared.speak(w.word)
                    } label: {
                        Image(systemName: "speaker.wave.2.fill")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.blue)
                }

                if showBack {
                    Divider()
                    Text(w.meaning)
                        .font(.headline)
                        .multilineTextAlignment(.center)
                    Button {
                        Speaker.shared.speak(w.example)
                    } label: {
                        Text(w.example)
                            .font(.footnote.italic())
                            .multilineTextAlignment(.center)
                    }
                    .buttonStyle(.plain)
                    Text(w.exampleZh)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    HStack(spacing: 4) {
                        gradeButton("忘了", .red, .again, w)
                        gradeButton("记得", .blue, .good, w)
                        gradeButton("简单", .green, .easy, w)
                    }
                    .padding(.top, 4)
                } else {
                    Button("显示释义") {
                        withAnimation { showBack = true }
                    }
                    .buttonStyle(.borderedProminent)
                    .padding(.top, 8)
                }
            }
        }
    }

    private func gradeButton(_ title: String, _ color: Color, _ rating: Rating, _ w: Word) -> some View {
        Button(title) {
            store.grade(w, rating)
            Haptics.play(rating == .again ? .failure : .success)
            if rating == .again {
                queue.append(w)  // 忘了的单词本轮最后再出现一次
            }
            showBack = false
            index += 1
            speakCurrent()
        }
        .font(.footnote)
        .buttonStyle(.bordered)
        .tint(color)
    }

    private func speakCurrent() {
        guard store.autoSpeak, index < queue.count else { return }
        Speaker.shared.speak(queue[index].word)
    }
}
