import SwiftUI

struct StatsView: View {
    @EnvironmentObject private var store: StudyStore
    @State private var confirmReset = false

    var body: some View {
        List {
            Section("进度") {
                row("连续学习", "\(store.currentStreak) 天")
                row("今日新学", "\(store.newTodayCount)")
                row("今日复习", "\(store.reviewedTodayCount)")
                row("已学单词", "\(store.learnedCount)/\(store.words.count)")
                row("已掌握", "\(store.masteredCount)")
                row("待复习", "\(store.dueCount)")
            }
            Section("设置") {
                Stepper("每日新词 \(store.dailyNewLimit)", value: $store.dailyNewLimit, in: 5...30, step: 5)
                Toggle("自动发音", isOn: $store.autoSpeak)
            }
            Section {
                Button("重置进度", role: .destructive) {
                    confirmReset = true
                }
            }
        }
        .navigationTitle("统计")
        .confirmationDialog("确定清空所有学习进度？", isPresented: $confirmReset) {
            Button("清空", role: .destructive) {
                store.resetProgress()
            }
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value).foregroundStyle(.secondary)
        }
    }
}
