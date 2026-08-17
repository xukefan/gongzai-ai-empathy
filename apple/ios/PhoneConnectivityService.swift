import Foundation
import WatchConnectivity
import GongzaiCore

struct ReceivedVoiceFile: Identifiable, Equatable {
    let id: UUID
    let eventID: UUID?
    let localURL: URL
}

@MainActor
final class PhoneConnectivityService: NSObject, ObservableObject {
    @Published private(set) var latestHeartbeat: HeartbeatPacket?
    @Published private(set) var latestVoiceFile: ReceivedVoiceFile?
    @Published private(set) var activationState: WCSessionActivationState = .notActivated
    @Published private(set) var lastErrorDescription: String?

    var isPaired: Bool {
        WCSession.isSupported() && WCSession.default.isPaired
    }

    var isWatchAppInstalled: Bool {
        WCSession.isSupported() && WCSession.default.isWatchAppInstalled
    }

    override init() {
        super.init()
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    func transfer(packet: HeartbeatPacket) {
        do {
            let payload = try GongzaiCoding.encoder().encode(packet)
            WCSession.default.transferUserInfo([
                "type": WatchMessageKind.heartbeatPacket.rawValue,
                "payload": payload
            ])
        } catch {
            lastErrorDescription = error.localizedDescription
        }
    }

    /// Sends a deterministic heartbeat to the paired Watch so one device pair
    /// can verify haptic playback without a backend or a second user.
    func sendDebugHeartbeat(bpm: Double) {
        do {
            let durationMS = 8_000
            let packet = HeartbeatPacket(
                senderID: "debug-iphone",
                receiverID: "debug-watch",
                averageBPM: bpm,
                beatIntervalsMS: try HeartbeatProcessing.syntheticIntervals(
                    averageBPM: bpm,
                    durationMS: durationMS
                ),
                recordedAt: Date(),
                durationMS: durationMS
            )
            transfer(packet: packet)
        } catch {
            lastErrorDescription = error.localizedDescription
        }
    }

    func sendAcknowledgement(eventID: UUID) {
        WCSession.default.transferUserInfo([
            "type": WatchMessageKind.acknowledgement.rawValue,
            "event_id": eventID.uuidString
        ])
    }

    private nonisolated static func persistTransferredFile(_ sourceURL: URL) throws -> URL {
        let fileManager = FileManager.default
        let baseURL = try fileManager.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let directory = baseURL.appendingPathComponent(
            "Gongzai/WatchTransfers",
            isDirectory: true
        )
        try fileManager.createDirectory(
            at: directory,
            withIntermediateDirectories: true
        )

        let destinationURL = directory
            .appendingPathComponent(UUID().uuidString)
            .appendingPathExtension(sourceURL.pathExtension.isEmpty ? "m4a" : sourceURL.pathExtension)
        try fileManager.copyItem(at: sourceURL, to: destinationURL)
        return destinationURL
    }
}

extension PhoneConnectivityService: WCSessionDelegate {
    nonisolated func session(
        _ session: WCSession,
        activationDidCompleteWith activationState: WCSessionActivationState,
        error: Error?
    ) {
        Task { @MainActor in
            self.activationState = activationState
            self.lastErrorDescription = error?.localizedDescription
        }
    }

    nonisolated func sessionDidBecomeInactive(_ session: WCSession) {}

    nonisolated func sessionDidDeactivate(_ session: WCSession) {
        session.activate()
    }

    nonisolated func session(
        _ session: WCSession,
        didReceiveUserInfo userInfo: [String: Any] = [:]
    ) {
        guard userInfo["type"] as? String == WatchMessageKind.heartbeatPacket.rawValue,
              let payload = userInfo["payload"] as? Data
        else {
            return
        }

        do {
            let packet = try GongzaiCoding.decoder().decode(
                HeartbeatPacket.self,
                from: payload
            )
            Task { @MainActor in
                self.latestHeartbeat = packet
            }
        } catch {
            Task { @MainActor in
                self.lastErrorDescription = error.localizedDescription
            }
        }
    }

    nonisolated func session(
        _ session: WCSession,
        didReceive file: WCSessionFile
    ) {
        do {
            let destinationURL = try Self.persistTransferredFile(file.fileURL)
            let eventID = (file.metadata?["event_id"] as? String).flatMap(UUID.init)
            let received = ReceivedVoiceFile(
                id: UUID(),
                eventID: eventID,
                localURL: destinationURL
            )
            Task { @MainActor in
                self.latestVoiceFile = received
            }
        } catch {
            Task { @MainActor in
                self.lastErrorDescription = error.localizedDescription
            }
        }
    }
}
