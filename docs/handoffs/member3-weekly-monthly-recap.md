# 成员 3：周报、月报与纪念日回顾代码整理

## 1. 功能范围

本功能对应产品方案第 4.6.3 节。服务端从当前有效关系双方已经确认、主动分享且未归档的生活瞬间中，按事件时间做事实汇总：

- 周报：以 `anchor_date` 所在自然周的周一 00:00 至下周周一 00:00 为统计窗口；
- 月报：以 `anchor_date` 所在自然月的第一天 00:00 至下月第一天 00:00 为统计窗口；
- 纪念日回顾：匹配历史记录中与 `anchor_date` 相同的月、日；
- 返回片段数量、记录日期、已保存标签计数、最多三条代表事件及全部来源 `event_id`；
- 不发送共同记忆库给 DeepSeek，不评价关系质量，也不根据心率、沉默或单次语音推断情绪。

## 2. 相关代码文件

| 文件 | 作用 | 是否必须部署 |
|---|---|:---:|
| `backend/recap_service.py` | 周报、月报、纪念日的时间窗口、数据筛选、标签统计和事实摘要 | 是 |
| `backend/main.py` | `GET /api/recaps/{period}` 路由、关系授权和响应包装 | 是 |
| `backend/models.py` | `Moment` 的确认转写、标签、记录时间、分享状态字段 | 是 |
| `backend/migrations/migrate_moment_record_fields.py` | 给旧数据库补齐 `Moment` 相关字段 | 旧库需要 |
| `backend/tests/test_recap_service.py` | 周、月、纪念日、权限过滤回归测试 | 否 |
| `fuwai/ai/contracts/recap-response.schema.json` | 回顾接口 JSON 响应契约 | 建议保留 |
| `docs/integration/member2-ai-asr-integration.md` | 成员 2 联调说明 | 建议保留 |

## 3. 核心代码入口

### 3.1 数据聚合

文件：`backend/recap_service.py`

```python
from recap_service import VALID_RECAP_PERIODS, build_recap

# period: "week"、"month" 或 "anniversary"
# visible_moments: 当前用户有权查看的已分享生活瞬间
recap = build_recap(period, visible_moments, anchor_date)
```

`build_recap()` 的输出包含：

```json
{
  "period": "month",
  "anchor_date": "2026-09-16",
  "period_start": "2026-09-01T00:00:00",
  "period_end": "2026-10-01T00:00:00",
  "total_moments": 2,
  "recorded_dates": ["2026-09-15", "2026-09-16"],
  "topics": [{"tag": "学习", "count": 2}],
  "fact_summary": "本月共保存 2 条已确认的共同记录，分布在 2 天。明确标签包括：学习（2）。",
  "representative_events": [],
  "source_event_ids": ["event-002", "event-001"],
  "generation_method": "deterministic_fact_aggregation",
  "schema_version": 1
}
```

### 3.2 HTTP 路由

文件：`backend/main.py`

```python
@app.get("/api/recaps/{period}", response_model=CommonResponse)
def get_recap(
    period: str,
    user_id: str,
    anchor_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    if period not in VALID_RECAP_PERIODS:
        raise HTTPException(status_code=422, detail="period must be week, month, or anniversary")
    if period == "anniversary" and anchor_date is None:
        raise HTTPException(status_code=422, detail="anniversary requires anchor_date in YYYY-MM-DD format")

    partner_id, visible = get_visible_shared_moments_query(user_id, db)
    recap = build_recap(period, visible.all(), anchor_date)
    return CommonResponse(
        code=0,
        msg="success",
        data={"user_id": user_id, "partner_id": partner_id, **recap},
    )
```

`get_visible_shared_moments_query()` 统一限制查询范围：

```python
Moment.user_id.in_([user_id, partner_id])
Moment.status.in_(["shared", "responded"])
Moment.confirmed_transcript.isnot(None)
Moment.shared_at.isnot(None)
```

因此，私有草稿、未确认转写、未主动分享记录、已归档记录，以及非当前关系用户的记录均不会进入回顾。

## 4. 调用示例

```text
GET /api/recaps/week?user_id=user_001&anchor_date=2026-09-16
GET /api/recaps/month?user_id=user_001&anchor_date=2026-09-16
GET /api/recaps/anniversary?user_id=user_001&anchor_date=2026-09-16
```

规则：

- 周报、月报的 `anchor_date` 可省略，默认当前日期；
- 纪念日回顾的 `anchor_date` 必填；
- `period` 不是 `week`、`month` 或 `anniversary` 时返回 HTTP `422`；
- 用户不存在 active 关系时返回 HTTP `403` 与 `TIMELINE_RELATIONSHIP_REQUIRED`。

## 5. 本地运行与测试

在仓库 `backend` 目录执行：

```powershell
D:\Python312\python.exe -m unittest tests\test_recap_service.py -v
```

已覆盖：

- 周报只统计当前自然周的可见片段；
- 月报严格使用自然月边界；
- 纪念日按同月同日跨年份匹配；
- 已归档、未确认、未分享和无权限记录不会出现；
- 关系解除后不能读取回顾。

完整后端回归测试：

```powershell
D:\Python312\python.exe -m unittest discover -s tests -v
```

## 6. 部署注意事项

新建数据库会由 `Base.metadata.create_all()` 创建完整表结构。已有旧数据库在备份后执行：

```powershell
cd backend
D:\Python312\python.exe migrations\migrate_moment_record_fields.py
```

当前仓库没有正式的登录鉴权中间件，成员 2 部署时必须将请求中的 `user_id` 与已登录用户绑定，不能直接信任客户端传来的任意用户 ID。
