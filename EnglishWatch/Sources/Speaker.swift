import AVFoundation
import WatchKit

/// 用系统语音朗读英文（手表扬声器或已连接的蓝牙耳机）
@MainActor
final class Speaker {
    static let shared = Speaker()
    private let synthesizer = AVSpeechSynthesizer()

    func speak(_ text: String, rate: Float = 0.45) {
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = rate
        synthesizer.speak(utterance)
    }
}

enum Haptics {
    @MainActor
    static func play(_ type: WKHapticType) {
        WKInterfaceDevice.current().play(type)
    }
}
