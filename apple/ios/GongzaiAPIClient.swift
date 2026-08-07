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
        body.append("Content-Type: audio/mp4\r\n\r\n")
        body.append(try Data(contentsOf: fileURL))
        body.append("\r\n--\(boundary)--\r\n")
        return body
    }

    private static func validate(response: URLResponse, body: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw GongzaiAPIError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let message = String(data: body, encoding: .utf8) ?? "无详细信息"
            throw GongzaiAPIError.rejected(
                statusCode: httpResponse.statusCode,
                message: message
            )
        }
    }
}

private extension Data {
    mutating func append(_ string: String) {
        append(Data(string.utf8))
    }
}
