import Foundation
import HealthKit
import GongzaiCore

@MainActor
final class HealthKitHeartRateRecorder: NSObject, ObservableObject {
    enum RecorderError: LocalizedError {
        case healthDataUnavailable
        case heartRateUnavailable
        case workoutSessionUnavailable
        case noHeartRateSamples

        var errorDescription: String? {
            switch self {
            case .healthDataUnavailable:
                return "此设备当前无法使用健康数据"
            case .heartRateUnavailable:
                return "无法读取心率数据类型"
            case .workoutSessionUnavailable:
                return "心率采集尚未启动"
            case .noHeartRateSamples:
                return "尚未读到心率，请贴紧佩戴并等待 8–15 秒"
            }
        }
    }

    @Published private(set) var currentBPM: Double?
    @Published private(set) var isCapturing = false
    @Published private(set) var sampleCount = 0
    @Published private(set) var lastErrorMessage: String?

    private let healthStore = HKHealthStore()
    private var workoutSession: HKWorkoutSession?
    private var workoutBuilder: HKLiveWorkoutBuilder?
    private var samples: [HeartRateSample] = []
    private var startedAt: Date?

    func requestAuthorization() async throws {
        guard HKHealthStore.isHealthDataAvailable() else {
            throw RecorderError.healthDataUnavailable
        }

        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            throw RecorderError.heartRateUnavailable
        }
        let workoutType = HKObjectType.workoutType()

        try await healthStore.requestAuthorization(
            toShare: [workoutType],
            read: [heartRateType]
        )
    }

    func startCapture() async throws {
        guard !isCapturing else { return }

        let configuration = HKWorkoutConfiguration()
        configuration.activityType = .other
        configuration.locationType = .unknown

        let session = try HKWorkoutSession(
            healthStore: healthStore,
            configuration: configuration
        )
        let builder = session.associatedWorkoutBuilder()
        builder.dataSource = HKLiveWorkoutDataSource(
            healthStore: healthStore,
            workoutConfiguration: configuration
        )
        session.delegate = self
        builder.delegate = self

        let start = Date()
        samples.removeAll(keepingCapacity: true)
        currentBPM = nil
        sampleCount = 0
        lastErrorMessage = nil
        startedAt = start
        workoutSession = session
        workoutBuilder = builder

        session.startActivity(with: start)
        do {
            try await withCheckedThrowingContinuation { continuation in
                builder.beginCollection(withStart: start) { success, error in
                    if success {
                        continuation.resume()
                    } else {
                        continuation.resume(
                            throwing: error ?? RecorderError.workoutSessionUnavailable
                        )
                    }
                }
            }
            isCapturing = true
            print("[HealthKit] Heart-rate collection started")
        } catch {
            session.end()
            workoutSession = nil
            workoutBuilder = nil
            startedAt = nil
            lastErrorMessage = error.localizedDescription
            throw error
        }
    }

    func stopCapture(senderID: String, receiverID: String) async throws -> HeartbeatPacket {
        guard isCapturing,
              let startedAt,
              let workoutSession,
              let workoutBuilder
        else {
            throw RecorderError.workoutSessionUnavailable
        }

        let endedAt = Date()
        workoutSession.end()
        await endCollection(builder: workoutBuilder, at: endedAt)

        self.workoutSession = nil
        self.workoutBuilder = nil
        self.startedAt = nil
        isCapturing = false

        guard !samples.isEmpty else {
            throw RecorderError.noHeartRateSamples
        }

        return try HeartbeatProcessing.makePacket(
            senderID: senderID,
            receiverID: receiverID,
            samples: samples,
            startedAt: startedAt,
            endedAt: endedAt
        )
    }

    private func endCollection(builder: HKLiveWorkoutBuilder, at date: Date) async {
        await withCheckedContinuation { continuation in
            builder.endCollection(withEnd: date) { _, _ in
                builder.discardWorkout()
                continuation.resume()
            }
        }
    }
}

extension HealthKitHeartRateRecorder: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didChangeTo toState: HKWorkoutSessionState,
        from fromState: HKWorkoutSessionState,
        date: Date
    ) {}

    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didFailWithError error: Error
    ) {
        Task { @MainActor in
            lastErrorMessage = error.localizedDescription
            isCapturing = false
            print("[HealthKit] Workout session failed: \(error.localizedDescription)")
        }
    }
}

extension HealthKitHeartRateRecorder: HKLiveWorkoutBuilderDelegate {
    nonisolated func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {}

    nonisolated func workoutBuilder(
        _ workoutBuilder: HKLiveWorkoutBuilder,
        didCollectDataOf collectedTypes: Set<HKSampleType>
    ) {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate),
              collectedTypes.contains(heartRateType),
              let quantity = workoutBuilder
                .statistics(for: heartRateType)?
                .mostRecentQuantity()
        else {
            return
        }

        let unit = HKUnit.count().unitDivided(by: .minute())
        let bpm = quantity.doubleValue(for: unit)
        guard HeartbeatProcessing.validBPMRange.contains(bpm) else { return }

        Task { @MainActor in
            currentBPM = bpm
            samples.append(HeartRateSample(bpm: bpm, capturedAt: Date()))
            sampleCount = samples.count
            print("[HealthKit] Received heart rate: \(bpm) BPM")
        }
    }
}
