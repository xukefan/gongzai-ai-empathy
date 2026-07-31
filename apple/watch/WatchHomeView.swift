import SwiftUI
import GongzaiCore

struct WatchHomeView: View {
    @AppStorage("senderID") private var senderID = "demo-user-a"
    @AppStorage("receiverID") private var receiverID = "demo-user-b"

    @StateObject private var heartRateRecorder = HealthKitHeartRateRecorder()
    @StateObject private var connectivity = WatchConnectivityService()
    @StateObject private var haptics = HeartbeatHapticPlayer()
    @StateObject private var audioRecorder = WatchAudioRecorder()

    @State private var pendingEventID = UUID()
    @State private var statusText = "准备就绪"

    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                Text(heartRateText)
                    .font(.title3.monospacedDigit())

                Button(heartRateRecorder.isCapturing ? "结束并发送" : "采集心率") {
                    Task {
                        await toggleHeartRateCapture()
                    }
                }

                Button(audioRecorder.isRecording ? "松开结束录音" : "录制原声") {
                    toggleRecording()
                }
                .tint(audioRecorder.isRecording ? .red : .blue)

                if let packet = connectivity.lastReceivedPacket {
                    Button("感受 \(Int(packet.averageBPM.rounded())) BPM") {
                        haptics.play(bpm: packet.averageBPM)
                    }
                }

                if connectivity.lastAcknowledgedEventID == pendingEventID {
                    Text("对方已收到")
                        .foregroundStyle(.green)
                }

                Text(statusText)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding()
        }
        .task {
            do {
                try await heartRateRecorder.requestAuthorization()
            } catch {
                statusText = "HealthKit 授权失败"
            }
        }
    }

    private var heartRateText: String {
        guard let bpm = heartRateRecorder.currentBPM else {
            return "-- BPM"
        }
        return "\(Int(bpm.rounded())) BPM"
    }

    private func toggleHeartRateCapture() async {
        do {
            if heartRateRecorder.isCapturing {
                let packet = try await heartRateRecorder.stopCapture(
                    senderID: senderID,
                    receiverID: receiverID
                )
                pendingEventID = packet.eventID
                try connectivity.transfer(packet: packet)
                statusText = "心率已交给 iPhone"
            } else {
                try heartRateRecorder.startCapture()
                statusText = "正在采集"
            }
        } catch {
            statusText = "心率采集失败"
        }
    }

    private func toggleRecording() {
        do {
            if audioRecorder.isRecording {
                guard let url = audioRecorder.stop() else {
                    statusText = "录音文件不可用"
                    return
                }
                connectivity.transferVoiceFile(url, eventID: pendingEventID)
                statusText = "原声已交给 iPhone"
            } else {
                try audioRecorder.start()
                statusText = "正在录音"
            }
        } catch {
            statusText = "录音失败"
        }
    }
}
