import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var store: StudyStore

    var body: some View {
        NavigationStack {
            List {
                NavigationLink {
                    StudyView()
                } label: {
                    Label("今日学习（\(store.dueCount + store.newRemaining)）", systemImage: "book.fill")
                }
                NavigationLink {
                    QuizView()
                } label: {
                    Label("小测验", systemImage: "checkmark.circle.fill")
                }
                NavigationLink {
                    StatsView()
                } label: {
                    Label("统计与设置", systemImage: "chart.bar.fill")
                }
                Text("🔥 连续学习 \(store.currentStreak) 天")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .listRowBackground(Color.clear)
            }
            .navigationTitle("背单词")
        }
    }
}
