import SwiftUI
import GongzaiCore

struct ContentView: View {
    private enum FocusField: Hashable {
        case apiBaseURL
        case userID
        case diaryContent
    }

    @AppStorage("apiBaseURL") private var apiBaseURL = "http://124.221.238.246:8000"
    @AppStorage("currentUserID") private var currentUserID = "demo-user-a"

    @StateObject private var connectivity = PhoneConnectivityService()
    @State private var statusText = "等待 Apple Watch 数据"
    @State private var isWorking = false
    @State private var isDNDEnabled = false
    @State private var diaryContent = ""
    @State private var moments: [BackendMoment] = []
    @FocusState private var focusedField: FocusField?

    var body: some View {
        NavigationStack {
            Form {
                Section("连接设置") {
                    TextField("后端地址", text: $apiBaseURL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($focusedField, equals: .apiBaseURL)
                        .submitLabel(.done)
                    TextField("当前用户 ID", text: $currentUserID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($focusedField, equals: .userID)
                        .submitLabel(.done)
                    Button("测试服务器连接") {
                        focusedField = nil
                        statusText = "正在连接服务器…"
                        Task { await checkServer() }
                    }
                    .disabled(isWorking)
                }

                Section("当前状态") {
                    HStack(spacing: 10) {
                        if isWorking {
                            ProgressView()
                        }
                        Text(statusText)
                            .textSelection(.enabled)
                    }
                }

                Section("AI 日记") {
                    Text("把这次发送的文字，或服务器转写后的原声内容放在这里，AI 会生成一条可回顾的日记。")
                        .font(.footnote)
                        .foregroundStyle(.secondary)

                    TextEditor(text: $diaryContent)
                        .focused($focusedField, equals: .diaryContent)
                        .frame(minHeight: 90)
                        .overlay(alignment: .topLeading) {
                            if diaryContent.isEmpty {
                                Text("例如：今天答辩结束了，虽然有点乱，但终于松了一口气。")
                                    .foregroundStyle(.tertiary)
                                    .padding(.top, 8)
                                    .padding(.leading, 5)
                                    .allowsHitTesting(false)
                            }
                        }

                    HStack {
                        Button("生成并保存 AI 日记") {
                            focusedField = nil
                            Task { await generateDiary() }
                        }
                        .disabled(isWorking || diaryContent.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)

                        Button("刷新") {
                            focusedField = nil
                            Task { await loadMoments() }
                        }
                        .disabled(isWorking)
                    }

                    if moments.isEmpty {
                        Text("还没有日记记录")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(moments) { moment in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(moment.title ?? "生活片段")
                                    .font(.headline)
                                if let summary = moment.summary, !summary.isEmpty {
                                    Text(summary)
                                        .font(.subheadline)
                                }
                                HStack(spacing: 8) {
                                    if let bpm = moment.bpm {
                                        Label("\(bpm) BPM", systemImage: "heart.fill")
                                    }
                                    Text(moment.createdAt)
                                }
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
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

                if let error = connectivity.lastErrorDescription {
                    Section("Apple Watch 错误") {
                        Text(error)
                            .foregroundStyle(.red)
                            .textSelection(.enabled)
                    }
                }
            }
            .navigationTitle("共在")
            .scrollDismissesKeyboard(.interactively)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("完成") {
                        focusedField = nil
                    }
                }
            }
            .onSubmit {
                focusedField = nil
            }
            .task {
                // Migrate devices that saved the old local development URL.
                if apiBaseURL == "http://127.0.0.1:8000" {
                    apiBaseURL = "http://124.221.238.246:8000"
                }
                await loadMoments()
            }
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

    @MainActor
    private func generateDiary() async {
        let content = diaryContent.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return }

        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            let moment = try await client.generateMoment(
                userID: currentUserID,
                content: content,
                bpm: latestBPM
            )
            moments.removeAll { $0.id == moment.id }
            moments.insert(moment, at: 0)
            diaryContent = ""
            statusText = moment.aiStatus == "fallback"
                ? "日记已保存（等待服务器配置 AI）"
                : "AI 日记已生成并保存"
        } catch {
            statusText = "AI 日记生成失败：\(error.localizedDescription)"
        }
    }

    @MainActor
    private func loadMoments() async {
        guard !isWorking else { return }
        isWorking = true
        defer { isWorking = false }

        do {
            let client = try GongzaiAPIClient(baseURLString: apiBaseURL)
            moments = try await client.fetchMoments(userID: currentUserID)
        } catch {
            // Do not replace the initial screen with an error when the server
            // is temporarily unavailable; the user can retry with “刷新”.
        }
    }

    private var latestBPM: Int? {
        guard let heartbeat = connectivity.latestHeartbeat else { return nil }
        return Int(heartbeat.averageBPM.rounded())
    }
}
