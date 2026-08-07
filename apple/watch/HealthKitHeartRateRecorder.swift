import Foundation
import HealthKit
import GongzaiCore

@MainActor
final class HealthKitHeartRateRecorder: NSObject, ObservableObject {
    enum RecorderError: Error {
        case heartRateUnavailable
        case workoutSessionUnavailable
    }

    @Published private(set) var currentBPM: Double?
    @Published private(set) var isCapturing = false
    @Published private(set) var lastError: Error?

    private let healthStore = HKHealthStore()
    private var workoutSession: HKWorkoutSession?
    private var workoutBuilder: HKLiveWorkoutBuilder?
    private var samples: [HeartRateSample] = []
    private var startedAt: Date?

    func requestAuthorization() async throws {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            throw RecorderError.heartRateUnavailable
        }

        try await healthStore.requestAuthorization(
            toShare: [],
            read: [heartRateType]
        )
    }

    func startCapture() throws {
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
        lastError = nil
        startedAt = start
        workoutSession = session
        workoutBuilder = builder
        isCapturing = true

        session.startActivity(with: start)
        builder.beginCollection(withStart: start) { [weak self] success, error in
            guard let self else { return }
            if !success, let error {
                Task { @MainActor in
                    self.lastError = error
                    self.isCapturing = false
                }
            }
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
            lastError = error
            isCapturing = false
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
        }
    }
}

