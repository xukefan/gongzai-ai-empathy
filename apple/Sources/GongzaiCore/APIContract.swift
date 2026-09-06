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
    public let transcriptionStatus: String?
    public let transcript: String?
    public let transcriptionError: String?
    public let transcriptionRequestID: String?

    enum CodingKeys: String, CodingKey {
        case voiceID = "voice_id"
        case status
        case aiStatus = "ai_status"
        case transcriptionStatus = "transcription_status"
        case transcript
        case transcriptionError = "transcription_error"
        case transcriptionRequestID = "transcription_request_id"
    }
}

public struct BackendTranscriptConfirmResponse: Codable, Equatable, Sendable {
    public let voiceID: String
    public let status: String
    public let transcript: String

    enum CodingKeys: String, CodingKey {
        case voiceID = "voice_id"
        case status
        case transcript
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

public struct BackendMomentGenerateRequest: Codable, Equatable, Sendable {
    public let userID: String
    public let content: String
    public let voiceID: String?
    public let bpm: Int?

    public init(
        userID: String,
        content: String,
        voiceID: String? = nil,
        bpm: Int? = nil
    ) {
        self.userID = userID
        self.content = content
        self.voiceID = voiceID
        self.bpm = bpm
    }

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case content
        case voiceID = "voice_id"
        case bpm
    }
}

public struct BackendMoment: Codable, Equatable, Identifiable, Sendable {
    public let id: String
    public let userID: String?
    public let title: String?
    public let summary: String?
    public let rawText: String?
    public let voiceID: String?
    public let bpm: Int?
    public let createdAt: String
    public let aiStatus: String?

    enum CodingKeys: String, CodingKey {
        case id
        case userID = "user_id"
        case title
        case summary
        case rawText = "raw_text"
        case voiceID = "voice_id"
        case bpm
        case createdAt = "created_at"
        case aiStatus = "ai_status"
    }
}

public struct BackendMomentCreateResponse: Codable, Equatable, Sendable {
    public let code: Int
    public let msg: String
    public let data: BackendMoment?
}

public struct BackendMomentsData: Codable, Equatable, Sendable {
    public let total: Int
    public let moments: [BackendMoment]
}

public struct BackendMomentsResponse: Codable, Equatable, Sendable {
    public let code: Int
    public let msg: String
    public let data: BackendMomentsData?
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
