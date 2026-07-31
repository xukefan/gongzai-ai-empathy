# XWR-666 后端提交审查

审查对象：提交 `f164b68`（第一周交付：后端基础接口 + 数据库 + 涂鸦集成）。

## 结论

该提交覆盖了 FastAPI、数据库模型、心跳接口、语音上传和涂鸦客户端的雏形，可以作为概念验证草稿，但目前不符合仓库安全、接口和协作规范，不能直接作为 Apple 端与挂件端的稳定联调基线。

## 阻断问题

| 级别 | 问题 | 处理要求 |
|---|---|---|
| Critical | 真实 Tuya Access ID 和 Access Secret 被写入公开提交 | 立即在涂鸦平台废止并重新生成；代码只从环境变量读取 |
| Critical | 密钥仍存在于公开 Git 历史和已提交的 Python 缓存中 | 新密钥不得复用；是否清理历史需负责人单独决定 |
| High | `tuya_client.py` 返回不存在的 `self.tokenN` | 已在当前修复分支改为 `self.token` |
| High | 仓库提交了 SQLite 数据库和 `__pycache__` | 从版本控制删除并加入 `.gitignore` |
| High | 音频上传无身份验证、大小/类型限制，路径设计近似公开静态文件 | 改为私有对象存储、短期访问地址和严格权限校验 |
| High | API 无用户认证与关系授权，可伪造 `user_id` 读取或写入数据 | 增加认证层，并在每个资源接口校验关系与所有权 |

## 接口与工程问题

- 直接推送到 `main`，未通过功能分支和 Pull Request；
- 提交信息不符合 `<type>(<scope>): <summary>` 规范；
- CORS 允许任意来源；
- 使用 `Base.metadata.create_all`，未提供 Alembic 迁移；
- `CreateMomentRequest` 在 `main.py` 内重复定义；
- 心跳字段使用 `bpm`、`pattern`，与文档中的 `average_bpm`、`beat_intervals_ms` 不一致；
- `Moment` 没有统一 `event_id`、接收方、转写状态和 `schema_version`；
- 设备事件通过“接收方最近一条事件”关联回应，存在串单风险，应显式携带 `event_id`；
- DND 状态只存在内存中，服务重启即丢失；
- 状态更新接受任意字符串，缺少枚举校验和状态机；
- 音频文件一次性读入内存，缺少流式写入、大小限制和 MIME 校验；
- 涂鸦签名实现尚未按官方 OpenAPI 流程完成验证；
- 没有测试、错误码文档、运行说明和 `.env.example`。

## Apple 与挂件端暂定联调边界

成员 1 的代码不直接依赖当前 FastAPI 实现细节，而通过独立 API Client 适配：

- Watch 内部模型使用 `average_bpm` 和 `beat_intervals_ms`；
- 发送现有后端时，由 API Client 临时映射为 `bpm` 和 `pattern`；
- 原声先在端侧保存为文件，再由 iPhone 上传；
- 挂件使用 `event_id` 接收和回传，不通过“最近一条事件”推断；
- 后端接口修正时，仅替换 API Client，不改 HealthKit、WatchConnectivity 和挂件状态机。

