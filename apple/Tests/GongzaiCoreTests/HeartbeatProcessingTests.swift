import Foundation
import XCTest
@testable import GongzaiCore

final class HeartbeatProcessingTests: XCTestCase {
    func testFiltersInvalidSamplesAndCalculatesAverage() throws {
        let now = Date()
        let samples = [
            HeartRateSample(bpm: 80, capturedAt: now),
            HeartRateSample(bpm: 82, capturedAt: now),
            HeartRateSample(bpm: 500, capturedAt: now)
        ]

        XCTAssertEqual(
            try HeartbeatProcessing.averageBPM(from: samples),
            81
        )
    }

    func testConvertsBPMToMilliseconds() throws {
        XCTAssertEqual(
            try HeartbeatProcessing.intervalMS(forBPM: 60),
            1_000
        )
        XCTAssertEqual(
            try HeartbeatProcessing.intervalMS(forBPM: 80),
            750
        )
        XCTAssertEqual(
            try HeartbeatProcessing.intervalMS(forBPM: 100),
            600
        )
    }

    func testBuildsCanonicalPacket() throws {
        let start = Date(timeIntervalSince1970: 100)
        let packet = try HeartbeatProcessing.makePacket(
            senderID: "user-a",
            receiverID: "user-b",
            samples: [
                HeartRateSample(bpm: 78, capturedAt: start),
                HeartRateSample(
                    bpm: 82,
                    capturedAt: start.addingTimeInterval(1)
                )
            ],
            startedAt: start,
            endedAt: start.addingTimeInterval(10)
        )

        XCTAssertEqual(packet.averageBPM, 80)
        XCTAssertEqual(packet.durationMS, 10_000)
        XCTAssertTrue(packet.beatIntervalsMS.allSatisfy { $0 == 750 })
        XCTAssertEqual(packet.schemaVersion, 1)
    }

    func testMapsPacketToExistingBackendContract() {
        let packet = HeartbeatPacket(
            senderID: "user-a",
            receiverID: "user-b",
            averageBPM: 82.4,
            beatIntervalsMS: [728, 735],
            recordedAt: Date(timeIntervalSince1970: 100),
            durationMS: 1_463
        )

        let request = BackendHeartbeatSendRequest(packet: packet)
        XCTAssertEqual(request.bpm, 82)
        XCTAssertEqual(request.pattern, "728,735")
    }

    func testDecodesHardenedBackendResponses() throws {
        let decoder = GongzaiCoding.decoder()

        let health = try decoder.decode(
            BackendHealthResponse.self,
            from: Data(#"{"status":"ok","service":"coglink-backend"}"#.utf8)
        )
        XCTAssertEqual(health.service, "coglink-backend")

        let dnd = try decoder.decode(
            BackendDNDResponse.self,
            from: Data(#"{"status":"ok","dnd_enabled":true}"#.utf8)
        )
        XCTAssertTrue(dnd.isEnabled)

        let deleted = try decoder.decode(
            BackendVoiceDeleteResponse.self,
            from: Data(#"{"status":"deleted","voice_id":"voice-1"}"#.utf8)
        )
        XCTAssertEqual(deleted.voiceID, "voice-1")
    }

    func testDecodesAIDiaryResponse() throws {
        let decoder = GongzaiCoding.decoder()
        let response = try decoder.decode(
            BackendMomentCreateResponse.self,
            from: Data(
                #"{"code":0,"msg":"AI日记已生成","data":{"id":"m-1","user_id":"user-a","title":"答辩结束后的松一口气","summary":"今天答辩结束了。","raw_text":"今天答辩终于结束了。","created_at":"2026-09-02T10:00:00","ai_status":"generated"}}"#.utf8
            )
        )

        XCTAssertEqual(response.code, 0)
        XCTAssertEqual(response.data?.id, "m-1")
        XCTAssertEqual(response.data?.title, "答辩结束后的松一口气")
        XCTAssertEqual(response.data?.aiStatus, "generated")
    }
}
