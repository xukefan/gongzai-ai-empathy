import Foundation

public enum GongzaiSchema {
    public static let currentVersion = 1
}

public struct HeartRateSample: Codable, Equatable, Sendable {
    public let bpm: Double
    public let capturedAt: Date

    public init(bpm: Double, capturedAt: Date) {
        self.bpm = bpm
        self.capturedAt = capturedAt
    }
}

public struct HeartbeatPacket: Codable, Equatable, Sendable {
    public let eventID: UUID
    public let senderID: String
    public let receiverID: String
    public let averageBPM: Double
    public let beatIntervalsMS: [Int]
    public let recordedAt: Date
    public let durationMS: Int
    public let schemaVersion: Int

    public init(
        eventID: UUID = UUID(),
        senderID: String,
        receiverID: String,
        averageBPM: Double,
        beatIntervalsMS: [Int],
        recordedAt: Date,
        durationMS: Int,
        schemaVersion: Int = GongzaiSchema.currentVersion
    ) {
        self.eventID = eventID
        self.senderID = senderID
        self.receiverID = receiverID
        self.averageBPM = averageBPM
        self.beatIntervalsMS = beatIntervalsMS
        self.recordedAt = recordedAt
        self.durationMS = durationMS
        self.schemaVersion = schemaVersion
    }
}

public enum MomentStatus: String, Codable, CaseIterable, Sendable {
    case created
    case uploaded
    case delivered
    case played
    case acknowledged
    case replied
    case failed
}

public struct VoiceAssetReference: Codable, Equatable, Sendable {
    public let id: String
    public let durationMS: Int
    public let transcript: String?

    public init(id: String, durationMS: Int, transcript: String? = nil) {
        self.id = id
        self.durationMS = durationMS
        self.transcript = transcript
    }
}

public struct MomentDraft: Codable, Equatable, Sendable {
    public let heartbeat: HeartbeatPacket
    public let voiceAsset: VoiceAssetReference?
    public let transcript: String?
    public let status: MomentStatus

    public init(
        heartbeat: HeartbeatPacket,
        voiceAsset: VoiceAssetReference? = nil,
        transcript: String? = nil,
        status: MomentStatus = .created
    ) {
        self.heartbeat = heartbeat
        self.voiceAsset = voiceAsset
        self.transcript = transcript
        self.status = status
    }
}

