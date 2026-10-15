import SwiftUI

struct QuizView: View {
    @EnvironmentObject private var store: StudyStore
    @State private var question: QuizQuestion?
    @State private var picked: Int?
    @State private var correct = 0
    @State private var total = 0

    var body: some View {
        ScrollView {
            if let q = question {
                VStack(spacing: 6) {
                    Text("答对 \(correct)/\(total)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                    Button {
                        Speaker.shared.speak(q.word.word)
                    } label: {
                        Label(q.word.word, systemImage: "speaker.wave.2.fill")
                            .font(.title3.bold())
                    }
                    .buttonStyle(.plain)

                    ForEach(q.options.indices, id: \.self) { i in
                        Button {
                            answer(i, q)
                        } label: {
                            Text(q.options[i])
                                .font(.footnote)
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.bordered)
                        .tint(color(for: i, in: q))
                        .disabled(picked != nil)
                    }

                    if picked != nil {
                        Button("下一题") { next() }
                            .buttonStyle(.borderedProminent)
                    }
                }
            } else {
                Text("单词库为空")
                    .foregroundStyle(.secondary)
            }
        }
        .navigationTitle("小测验")
        .onAppear {
            if question == nil { next() }
        }
    }

    private func answer(_ i: Int, _ q: QuizQuestion) {
        picked = i
        total += 1
        let ok = i == q.answer
        if ok { correct += 1 }
        Haptics.play(ok ? .success : .failure)
        store.recordQuiz(q.word, correct: ok)
    }

    private func next() {
        picked = nil
        question = store.makeQuiz()
        if store.autoSpeak, let w = question?.word {
            Speaker.shared.speak(w.word)
        }
    }

    private func color(for i: Int, in q: QuizQuestion) -> Color {
        guard let picked else { return .gray }
        if i == q.answer { return .green }
        return i == picked ? .red : .gray
    }
}
