import Foundation

/// Temporary adapter for the backend currently present on `main`.
/// The Apple app keeps its internal model canonical and maps only at the API boundary.
public struct BackendHeartbeatSendRequest: Codable, Equatable, Sendable {
    public let senderID: String
    public let receiverID: String
    public let bpm: Int
    public let pattern: String?

    public init(packet: HeartbeatPacket) {
        senderID = packet.senderID
        receiverID = packet.receiverID
        bpm = Int(packet.averageBPM.rounded())
        pattern = packet.beatIntervalsMS.map(String.init).joined(separator: ",")
    }

    enum CodingKeys: String, CodingKey {
        case senderID = "sender_id"
        case receiverID = "receiver_id"
        case bpm
        case pattern
    }
}

public struct BackendHeartbeatSendResponse: Codable, Equatable, Sendable {
    public let eventID: String
    public let status: String
    public let message: String?

    enum CodingKeys: String, CodingKey {
        case eventID = "event_id"
        case status
        case message
    }
}

public struct BackendVoiceUploadResponse: Codable, Equatable, Sendable {
    public let voiceID: String
    public let status: String
    public let aiStatus: String?

    enum CodingKeys: String, CodingKey {
        case voiceID = "voice_id"
        case status
        case aiStatus = "ai_status"
    }
}

public struct BackendHealthResponse: Codable, Equatable, Sendable {
    public let status: String
    public let service: String
}

public struct BackendVoiceDeleteResponse: Codable, Equatable, Sendable {
    public let status: String
    public let voiceID: String

    enum CodingKeys: String, CodingKey {
        case status
        case voiceID = "voice_id"
    }
}

public struct BackendDNDResponse: Codable, Equatable, Sendable {
    public let status: String?
    public let isEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case status
        case isEnabled = "dnd_enabled"
    }
}

public struct BackendErrorResponse: Codable, Equatable, Sendable {
    public let detail: String
}

public enum WatchMessageKind: String, Codable, Sendable {
    case heartbeatPacket = "heartbeat_packet"
    case acknowledgement
    case voiceReady = "voice_ready"
}

public enum GongzaiCoding {
    public static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }

    public static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}
