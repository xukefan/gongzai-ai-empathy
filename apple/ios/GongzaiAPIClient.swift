import Foundation
import Combine
import Security
import GongzaiCore

struct BackendAuthUser: Codable, Equatable, Sendable {
    let id: String
    let username: String
    let phone: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, username, phone
        case createdAt = "created_at"
    }
}

struct BackendAuthResponse: Codable, Equatable, Sendable {
    let accessToken: String
    let tokenType: String
    let expiresAt: Int
    let user: BackendAuthUser

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
        case expiresAt = "expires_at"
        case user
    }
}

private struct RegisterPayload: Encodable {
    let username: String
    let password: String
    let phone: String?
}

private struct LoginPayload: Encodable {
    let username: String
    let password: String
}

/// Stores only the bearer token in Keychain; no password is retained on the
/// device.  The user id is a non-sensitive convenience value used to build
/// requests and is restored from UserDefaults.
@MainActor
final class AuthSession: ObservableObject {
    @Published private(set) var accessToken: String?
    @Published private(set) var user: BackendAuthUser?

    private let defaults = UserDefaults.standard
    private let keychain = KeychainTokenStore()

    init() {
        accessToken = keychain.read()
        if let userID = defaults.string(forKey: "auth.userID"),
           let username = defaults.string(forKey: "auth.username") {
            user = BackendAuthUser(
                id: userID,
                username: username,
                phone: defaults.string(forKey: "auth.phone"),
                createdAt: defaults.string(forKey: "auth.createdAt")
            )
        }
    }

    var isAuthenticated: Bool { accessToken != nil && user != nil }

    func save(_ response: BackendAuthResponse) {
        keychain.save(response.accessToken)
        accessToken = response.accessToken
        user = response.user
        defaults.set(response.user.id, forKey: "auth.userID")
        defaults.set(response.user.username, forKey: "auth.username")
        defaults.set(response.user.phone, forKey: "auth.phone")
        defaults.set(response.user.createdAt, forKey: "auth.createdAt")
    }

    func logout() {
        keychain.delete()
        accessToken = nil
        user = nil
        defaults.removeObject(forKey: "auth.userID")
        defaults.removeObject(forKey: "auth.username")
        defaults.removeObject(forKey: "auth.phone")
        defaults.removeObject(forKey: "auth.createdAt")
    }
}

private struct KeychainTokenStore {
    private let service = "io.github.xukefan.gongzai.auth"
    private let account = "access-token"

    func read() -> String? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func save(_ token: String) {
        let data = Data(token.utf8)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        let attributes: [String: Any] = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = data
            SecItemAdd(item as CFDictionary, nil)
        }
    }

    func delete() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}

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
    let accessToken: String?

    init(
        baseURLString: String,
        session: URLSession = .shared,
        accessToken: String? = nil
    ) throws {
        guard let url = URL(string: baseURLString),
              let scheme = url.scheme,
              ["http", "https"].contains(scheme)
        else {
            throw GongzaiAPIError.invalidBaseURL
        }
        self.baseURL = url
        self.session = session
        self.accessToken = accessToken
    }

    func register(
        username: String,
        password: String,
        phone: String? = nil
    ) async throws -> BackendAuthResponse {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/auth/register"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try GongzaiCoding.encoder().encode(
            RegisterPayload(username: username, password: password, phone: phone)
        )
        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(BackendAuthResponse.self, from: data)
    }

    func login(username: String, password: String) async throws -> BackendAuthResponse {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/auth/login"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try GongzaiCoding.encoder().encode(
            LoginPayload(username: username, password: password)
        )
        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(BackendAuthResponse.self, from: data)
    }

    func currentUser() async throws -> BackendAuthUser {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/auth/me"))
        request.timeoutInterval = 10
        request = authorized(request)
        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(BackendAuthUser.self, from: data)
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
        packet: HeartbeatPacket,
        senderID: String? = nil,
        receiverID: String? = nil
    ) async throws -> BackendHeartbeatSendResponse {
        var request = URLRequest(
            url: baseURL.appendingPathComponent("api/heartbeat/send")
        )
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try GongzaiCoding.encoder().encode(
            BackendHeartbeatSendRequest(
                packet: packet,
                senderID: senderID,
                receiverID: receiverID
            )
        )
        request = authorized(request)

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
        request = authorized(request)

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendVoiceUploadResponse.self,
            from: data
        )
    }

    func confirmTranscript(
        voiceID: String,
        userID: String
    ) async throws -> BackendTranscriptConfirmResponse {
        let url = try queryURL(
            path: "api/voice/\(voiceID)/transcript/confirm",
            items: [URLQueryItem(name: "user_id", value: userID)]
        )
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 15
        request = authorized(request)

        let (data, response) = try await session.data(for: request)
        try Self.validate(response: response, body: data)
        return try GongzaiCoding.decoder().decode(
            BackendTranscriptConfirmResponse.self,
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

        let (data, response) = try await session.data(for: authorized(URLRequest(url: url)))
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
        request = authorized(request)
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
        let (data, response) = try await session.data(for: authorized(URLRequest(url: url)))
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
        request = authorized(request)
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
        request = authorized(request)

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
        request = authorized(request)

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

    private func authorized(_ request: URLRequest) -> URLRequest {
        var request = request
        if let accessToken, !accessToken.isEmpty {
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }
        return request
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
