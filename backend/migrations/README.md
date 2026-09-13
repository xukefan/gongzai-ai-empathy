# 生活瞬间数据库迁移

`migrate_moment_record_fields.py` 为第 4.6.1 节增加生活瞬间完整记录字段：原始/确认转写、AI 结构化结果、BPM、媒体引用、备注、确认与回复引用等。

在后端目录执行：

```powershell
python migrations\migrate_moment_record_fields.py
```

迁移只执行新增字段和索引，不删除、不覆盖已有 `moments` 数据；重复执行不会重复添加字段。生产环境执行前应由成员 2 先备份数据库，并在与实际数据库类型相同的测试环境验证。

新建数据库不需要单独执行迁移：`models.py` 中的 `Base.metadata.create_all()` 会直接创建完整表结构。
