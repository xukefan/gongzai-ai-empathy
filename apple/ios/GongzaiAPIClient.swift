import Foundation
import GongzaiCore

enum GongzaiAPIError: LocalizedError {
    case invalidBaseURL
    case invalidResponse
    case rejected(statusCode: Int, message: String)

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "服务器地址无效"
        case .invalidResponse:
            return "服务器返回了无法识别的响应"
        case let .rejected(statusCode, message):
            return "请求失败（\(statusCode)）：\(message)"
        }
    }
}

struct GongzaiAPIClient {
    let baseURL: URL
    var session: URLSession = .shared

    init(baseURLString: String, session: URLSession = .shared) throws {
        guard let url = URL(string: baseURLString),
              let scheme = url.scheme,
              ["http", "https"].contains(scheme)
        else {
            throw GongzaiAPIError.invalidBaseURL
        }
        self.baseURL = url
        self.session = session
    }

    func healthCheck() async throws -> BackendHealthResponse {
        var request = URLRequest(
            url: baseURL.appendingPathComponent("api/health")
        )
        // Do not leave the UI looking frozen when a device cannot reach the host.
        request.timeoutInterval = 10
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendHealthResponse.self,
            from: data
        )
    }

    func sendHeartbeat(
        packet: HeartbeatPacket
    ) async throws -> BackendHeartbeatSendResponse {
        var request = URLRequest(
            url: baseURL.appendingPathComponent("api/heartbeat/send")
        )
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try GongzaiCoding.encoder().encode(
            BackendHeartbeatSendRequest(packet: packet)
        )

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendHeartbeatSendResponse.self,
            from: data
        )
    }

    func uploadVoice(
        fileURL: URL,
        userID: String,
        durationMS: Int
    ) async throws -> BackendVoiceUploadResponse {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("api/voice/upload"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [
            URLQueryItem(name: "user_id", value: userID),
            URLQueryItem(
                name: "duration",
                value: String(max(1, durationMS / 1_000))
            )
        ]
        guard let url = components?.url else {
            throw GongzaiAPIError.invalidBaseURL
        }

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(
            "multipart/form-data; boundary=\(boundary)",
            forHTTPHeaderField: "Content-Type"
        )
        request.httpBody = try Self.multipartBody(
            fileURL: fileURL,
            boundary: boundary
        )

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendVoiceUploadResponse.self,
            from: data
        )
    }

    func downloadVoice(voiceID: String, userID: String) async throws -> Data {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("api/voice/\(voiceID)"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [URLQueryItem(name: "user_id", value: userID)]
        guard let url = components?.url else {
            throw GongzaiAPIError.invalidBaseURL
        }

        let (data, response) = try await session.data(from: url)
        try Self.validate(response: response, body: data)
        return data
    }

    func deleteVoice(voiceID: String, userID: String) async throws {
        var components = URLComponents(
            url: baseURL.appendingPathComponent("api/voice/\(voiceID)"),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = [URLQueryItem(name: "user_id", value: userID)]
        guard let url = components?.url else {
            throw GongzaiAPIError.invalidBaseURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        _ = try GongzaiCoding.decoder().decode(
            BackendVoiceDeleteResponse.self,
            from: data
        )
    }

    func dndStatus(userID: String) async throws -> BackendDNDResponse {
        let url = try queryURL(
            path: "api/dnd/status",
            items: [URLQueryItem(name: "user_id", value: userID)]
        )
        let (data, response) = try await session.data(from: url)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendDNDResponse.self,
            from: data
        )
    }

    func setDND(userID: String, enabled: Bool) async throws -> BackendDNDResponse {
        let url = try queryURL(
            path: "api/dnd/set",
            items: [
                URLQueryItem(name: "user_id", value: userID),
                URLQueryItem(name: "enabled", value: enabled ? "true" : "false")
            ]
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendDNDResponse.self,
            from: data
        )
    }

    func generateMoment(
        userID: String,
        content: String,
        voiceID: String? = nil,
        bpm: Int? = nil
    ) async throws -> BackendMoment {
        var request = URLRequest(
            url: baseURL.appendingPathComponent("api/moments/generate")
        )
        request.httpMethod = "POST"
        request.timeoutInterval = 30
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try GongzaiCoding.encoder().encode(
            BackendMomentGenerateRequest(
                userID: userID,
                content: content,
                voiceID: voiceID,
                bpm: bpm
            )
        )

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        let envelope = try GongzaiCoding.decoder().decode(
            BackendMomentCreateResponse.self,
            from: data
        )
        try Self.validate(envelope: envelope.code, message: envelope.msg)
        guard let moment = envelope.data else {
            throw GongzaiAPIError.invalidResponse
        }
        return moment
    }

    func fetchMoments(
        userID: String,
        limit: Int = 20,
        offset: Int = 0
    ) async throws -> [BackendMoment] {
        let url = try queryURL(
            path: "api/moments",
            items: [
                URLQueryItem(name: "user_id", value: userID),
                URLQueryItem(name: "limit", value: String(max(1, min(limit, 100)))),
                URLQueryItem(name: "offset", value: String(max(0, offset)))
            ]
        )
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        request.cachePolicy = .reloadIgnoringLocalCacheData

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        let envelope = try GongzaiCoding.decoder().decode(
            BackendMomentsResponse.self,
            from: data
        )
        try Self.validate(envelope: envelope.code, message: envelope.msg)
        return envelope.data?.moments ?? []
    }

    private func queryURL(path: String, items: [URLQueryItem]) throws -> URL {
        var components = URLComponents(
            url: baseURL.appendingPathComponent(path),
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = items
        guard let url = components?.url else {
            throw GongzaiAPIError.invalidBaseURL
        }
        return url
    }

    private static func multipartBody(
        fileURL: URL,
        boundary: String
    ) throws -> Data {
        var body = Data()
        body.append("--\(boundary)\r\n")
        body.append(
            "Content-Disposition: form-data; name=\"file\"; " +
            "filename=\"\(fileURL.lastPathComponent)\"\r\n"
        )
        body.append("Content-Type: \(contentType(for: fileURL))\r\n\r\n")
        body.append(try Data(contentsOf: fileURL))
        body.append("\r\n--\(boundary)--\r\n")
        return body
    }

    private static func validate(response: URLResponse, body: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw GongzaiAPIError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let message = (
                try? GongzaiCoding.decoder().decode(
                    BackendErrorResponse.self,
                    from: body
                ).detail
            ) ?? String(data: body, encoding: .utf8) ?? "无详细信息"
            throw GongzaiAPIError.rejected(
                statusCode: httpResponse.statusCode,
                message: message
            )
        }
    }

    private static func validate(envelope code: Int, message: String) throws {
        guard code == 0 else {
            throw GongzaiAPIError.rejected(statusCode: code, message: message)
        }
    }

    private static func contentType(for fileURL: URL) -> String {
        switch fileURL.pathExtension.lowercased() {
        case "wav":
            return "audio/wav"
        case "mp3":
            return "audio/mpeg"
        case "aac":
            return "audio/aac"
        default:
            return "audio/mp4"
        }
    }
}

private extension Data {
    mutating func append(_ string: String) {
        append(Data(string.utf8))
    }
}
