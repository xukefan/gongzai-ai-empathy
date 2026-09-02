import Foundation
import WatchConnectivity
import GongzaiCore

@MainActor
final class WatchConnectivityService: NSObject, ObservableObject {
    @Published private(set) var lastReceivedPacket: HeartbeatPacket?
    @Published private(set) var lastAcknowledgedEventID: UUID?
    @Published private(set) var lastError: Error?

    override init() {
        super.init()
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    func transfer(packet: HeartbeatPacket) throws {
        let payload = try GongzaiCoding.encoder().encode(packet)
        WCSession.default.transferUserInfo([
            "type": WatchMessageKind.heartbeatPacket.rawValue,
            "payload": payload
        ])
    }

    func transferVoiceFile(_ url: URL, eventID: UUID) {
        WCSession.default.transferFile(
            url,
            metadata: [
                "type": WatchMessageKind.voiceReady.rawValue,
                "event_id": eventID.uuidString
            ]
        )
    }
}

extension WatchConnectivityService: WCSessionDelegate {
    nonisolated func session(
        _ session: WCSession,
        activationDidCompleteWith activationState: WCSessionActivationState,
        error: Error?
    ) {
        guard let error else { return }
        Task { @MainActor in
            lastError = error
        }
    }

    nonisolated func session(
        _ session: WCSession,
        didReceiveUserInfo userInfo: [String: Any] = [:]
    ) {
        if userInfo["type"] as? String == WatchMessageKind.acknowledgement.rawValue,
           let rawEventID = userInfo["event_id"] as? String,
           let eventID = UUID(uuidString: rawEventID) {
            Task { @MainActor in
                lastAcknowledgedEventID = eventID
            }
            return
        }

        guard userInfo["type"] as? String == WatchMessageKind.heartbeatPacket.rawValue,
              let payload = userInfo["payload"] as? Data,
              let packet = try? GongzaiCoding.decoder().decode(
                  HeartbeatPacket.self,
                  from: payload
              )
        else {
            return
        }

        Task { @MainActor in
            lastReceivedPacket = packet
        }
    }
}
