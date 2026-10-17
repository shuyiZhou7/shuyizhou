import SwiftUI

@main
struct EnglishWatchApp: App {
    @StateObject private var store = StudyStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
