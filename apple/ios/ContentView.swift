import SwiftUI
import GongzaiCore

struct ContentView: View {
    @AppStorage("apiBaseURL") private var apiBaseURL = "http://127.0.0.1:8000"
    @AppStorage("currentUserID") private var currentUserID = "demo-user-a"

    @StateObject private var connectivity = PhoneConnectivityService()
    @State private var statusText = "等待 Apple Watch 数据"
    @State private var isWorking = false

    var body: some View {
        NavigationStack {
            Form {
                Section("连接设置") {
                    TextField("后端地址", text: $apiBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    TextField("当前用户 ID", text: $currentUserID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }

                Section("Apple Watch") {
                    LabeledContent("连接状态", value: activationLabel)

                    if let packet = connectivity.latestHeartbeat {
                        LabeledContent(
                            "最近心率",
                            value: "\(Int(packet.averageBPM.rounded())) BPM"
                        )
                        Button("发送到服务器") {
                            Task { await send(packet: packet) }
                        }
                        .disabled(isWorking)
                    } else {
                        Text("尚未收到心率片段")
                            .foregroundStyle(.secondary)
                    }

                    if connectivity.latestVoiceFile != nil {
                        Button("上传原声并进入转写队列") {
                            Task { await uploadLatestVoice() }
                        }
                        .disabled(isWorking)
                    }
                }

                Section("状态") {
                    Text(statusText)
                    if let error = connectivity.lastErrorDescription {
                        Text(error)
                            .foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("共在")
        }
    }

    private var activationLabel: String {
        switch connectivity.activationState {
        case .activated:
            return "已激活"
        case .inactive:
            return "未激活"
        case .notActivated:
            return "等待激活"
        @unknown default:
            return "未知"
        }
    }

    @MainActor
    private func send(packet: HeartbeatPacket) async {
        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            let response = try await client.sendHeartbeat(packet: packet)
            statusText = response.status == "ok"
                ? "心率已提交：\(response.eventID)"
                : (response.message ?? "后端未接受心率")
        } catch {
            statusText = error.localizedDescription
        }
    }

    @MainActor
    private func uploadLatestVoice() async {
        guard let voice = connectivity.latestVoiceFile else { return }
        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            let response = try await client.uploadVoice(
                fileURL: voice.localURL,
                userID: currentUserID,
                durationMS: 10_000
            )
            statusText = "原声已上传：\(response.voiceID)，等待服务器转写"
        } catch {
            statusText = error.localizedDescription
        }
    }
}
