import AVFoundation
import Foundation

@MainActor
final class WatchAudioRecorder: NSObject, ObservableObject {
    enum RecordingError: Error {
        case alreadyRecording
        case recorderUnavailable
    }

    @Published private(set) var isRecording = false
    @Published private(set) var lastRecordingURL: URL?

    private var recorder: AVAudioRecorder?

    func start() throws {
        guard !isRecording else {
            throw RecordingError.alreadyRecording
        }

        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.record, mode: .default)
        try session.setActive(true)

        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("gongzai-watch-recordings", isDirectory: true)
        try FileManager.default.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )

        let url = directory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension("m4a")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
        ]

        let recorder = try AVAudioRecorder(url: url, settings: settings)
        recorder.delegate = self
        recorder.prepareToRecord()
        guard recorder.record() else {
            throw RecordingError.recorderUnavailable
        }

        self.recorder = recorder
        lastRecordingURL = nil
        isRecording = true
    }

    @discardableResult
    func stop() -> URL? {
        guard let recorder else { return nil }
        recorder.stop()
        self.recorder = nil
        isRecording = false
        lastRecordingURL = recorder.url
        try? AVAudioSession.sharedInstance().setActive(false)
        return recorder.url
    }
}

extension WatchAudioRecorder: AVAudioRecorderDelegate {
    nonisolated func audioRecorderEncodeErrorDidOccur(
        _ recorder: AVAudioRecorder,
        error: Error?
    ) {
        Task { @MainActor in
            self.recorder = nil
            self.isRecording = false
        }
    }
}

