import Foundation

public enum HeartbeatProcessingError: Error, Equatable {
    case noValidSamples
    case invalidDuration
    case invalidUserID
}

public enum HeartbeatProcessing {
    public static let validBPMRange = 30.0 ... 240.0

    public static func validSamples(from samples: [HeartRateSample]) -> [HeartRateSample] {
        samples.filter { validBPMRange.contains($0.bpm) }
    }

    public static func averageBPM(from samples: [HeartRateSample]) throws -> Double {
        let valid = validSamples(from: samples)
        guard !valid.isEmpty else {
            throw HeartbeatProcessingError.noValidSamples
        }

        return valid.reduce(0) { $0 + $1.bpm } / Double(valid.count)
    }

    public static func intervalMS(forBPM bpm: Double) throws -> Int {
        guard validBPMRange.contains(bpm) else {
            throw HeartbeatProcessingError.noValidSamples
        }

        return Int((60_000.0 / bpm).rounded())
    }

    public static func syntheticIntervals(
        averageBPM: Double,
        durationMS: Int
    ) throws -> [Int] {
        guard durationMS > 0 else {
            throw HeartbeatProcessingError.invalidDuration
        }

        let interval = try intervalMS(forBPM: averageBPM)
        let beatCount = max(1, durationMS / interval)
        return Array(repeating: interval, count: beatCount)
    }

    public static func makePacket(
        senderID: String,
        receiverID: String,
        samples: [HeartRateSample],
        startedAt: Date,
        endedAt: Date
    ) throws -> HeartbeatPacket {
        guard !senderID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              !receiverID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        else {
            throw HeartbeatProcessingError.invalidUserID
        }

        let durationMS = Int(endedAt.timeIntervalSince(startedAt) * 1_000)
        guard durationMS > 0 else {
            throw HeartbeatProcessingError.invalidDuration
        }

        let average = try averageBPM(from: samples)
        let intervals = try syntheticIntervals(
            averageBPM: average,
            durationMS: durationMS
        )

        return HeartbeatPacket(
            senderID: senderID,
            receiverID: receiverID,
            averageBPM: average,
            beatIntervalsMS: intervals,
            recordedAt: startedAt,
            durationMS: durationMS
        )
    }
}

