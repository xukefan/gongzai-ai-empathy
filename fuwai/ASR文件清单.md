# ASR 文件清单

该目录包含成员 3 负责的“讯飞录音文件转写大模型”服务代码与集成材料。

## 服务代码

- `ai/asr_api.py`：FastAPI 路由，提供 `POST /internal/ai/asr`。
- `ai/asr_service.py`：统一的业务响应和错误映射。
- `ai/iflytek_file_asr.py`：讯飞 `/v2/upload` 与 `/v2/getResult` 客户端。
- `ai/asr_client_example.py`：成员 2 调用接口的 Python 示例。

## 配置与部署

- `ai/.env.example`：讯飞和内部接口配置模板；复制为 `.env` 后填写，禁止提交真实密钥。
- `ai/requirements.txt`：Python 依赖。
- `ai/deploy/nginx-asr.conf.example`：HTTPS 反向代理模板。

## 接口说明与测试

- `ai/contracts/asr-https-integration.md`：成员 2 的完整 HTTPS 调用契约。
- `ai/contracts/asr-request.schema.json`：请求元数据 Schema。
- `ai/contracts/asr-response.schema.json`：响应 Schema。
- `ai/contracts/iflytek-file-asr.md`：讯飞官方接口字段映射说明。
- `ai/tests/test_iflytek_file_asr.py`：离线单元测试。

## 不包含的内容

- 不包含任何真实 `.env`、讯飞 `APISecret`、SSH 私钥或录音文件。
- 不包含旧的实时 WebSocket ASR 参考代码，正式方案只使用录音文件转写大模型。
