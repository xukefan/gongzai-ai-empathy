import Foundation
import WatchKit

@MainActor
final class HeartbeatHapticPlayer: ObservableObject {
    @Published private(set) var isPlaying = false

    private var playbackTask: Task<Void, Never>?

    func play(bpm: Double, beatCount: Int = 8) {
        stop()
        guard (30 ... 240).contains(bpm), beatCount > 0 else { return }

        isPlaying = true
        let intervalNanoseconds = UInt64((60.0 / bpm) * 1_000_000_000)

        playbackTask = Task { [weak self] in
            for index in 0 ..< beatCount {
                guard !Task.isCancelled else { break }
                WKInterfaceDevice.current().play(.click)

                if index < beatCount - 1 {
                    try? await Task.sleep(nanoseconds: intervalNanoseconds)
                }
            }

            guard !Task.isCancelled else { return }
            self?.isPlaying = false
        }
    }

    func stop() {
        playbackTask?.cancel()
        playbackTask = nil
        isPlaying = false
    }
}

