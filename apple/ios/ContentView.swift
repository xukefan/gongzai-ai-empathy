import SwiftUI
import GongzaiCore

struct ContentView: View {
    @AppStorage("apiBaseURL") private var apiBaseURL = "http://127.0.0.1:8000"
    @AppStorage("currentUserID") private var currentUserID = "demo-user-a"

    @StateObject private var connectivity = PhoneConnectivityService()
    @State private var statusText = "等待 Apple Watch 数据"
    @State private var isWorking = false
    @State private var isDNDEnabled = false

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
                    Button("测试服务器连接") {
                        Task { await checkServer() }
                    }
                    .disabled(isWorking)
                }

                Section("隐私与勿扰") {
                    Toggle("勿扰模式", isOn: $isDNDEnabled)
                    HStack {
                        Button("读取服务器设置") {
                            Task { await loadDND() }
                        }
                        Button("保存") {
                            Task { await saveDND() }
                        }
                    }
                    .disabled(isWorking)
                }

                Section("Apple Watch") {
                    LabeledContent("连接状态", value: activationLabel)
                    LabeledContent("已配对", value: connectivity.isPaired ? "是" : "否")
                    LabeledContent(
                        "Watch App",
                        value: connectivity.isWatchAppInstalled ? "已安装" : "未安装"
                    )

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

#if DEBUG
                Section("单机调试") {
                    Text("向配对的 Apple Watch 发送测试节奏，无需服务器或第二位用户。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    HStack {
                        ForEach([60.0, 80.0, 100.0], id: \.self) { bpm in
                            Button("\(Int(bpm)) BPM") {
                                connectivity.sendDebugHeartbeat(bpm: bpm)
                                statusText = "已排队发送 \(Int(bpm)) BPM 测试节奏"
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
#endif

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
    private func checkServer() async {
        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            let result = try await client.healthCheck()
            statusText = result.status == "ok"
                ? "服务器已连接：\(result.service)"
                : "服务器状态异常：\(result.status)"
        } catch {
            statusText = error.localizedDescription
        }
    }

    @MainActor
    private func loadDND() async {
        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            let result = try await client.dndStatus(userID: currentUserID)
            isDNDEnabled = result.isEnabled
            statusText = "已读取服务器勿扰设置"
        } catch {
            statusText = error.localizedDescription
        }
    }

    @MainActor
    private func saveDND() async {
        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            let result = try await client.setDND(
                userID: currentUserID,
                enabled: isDNDEnabled
            )
            isDNDEnabled = result.isEnabled
            statusText = "勿扰设置已保存"
        } catch {
            statusText = error.localizedDescription
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
