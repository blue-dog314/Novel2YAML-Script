# MVP 计划

## 目标

P0a-lite 的目标是把 3 章或以上小说文本转换为结构化、可编辑、可校验的 screenplay YAML 草稿。

当前阶段聚焦 P0a-lite-1：最小生成闭环，不做完整 Web 编辑器、多人协作、PDF/DOCX/Final Draft 导出、Story Bible 或场景级局部重生成。

## P0a-lite-1 范围

已实现后端闭环骨架：

1. `shared_types`: 跨包契约层。
2. `screenplay_schema`: JSON Schema 和静态 schema 文档产物。
3. `validators`: YAML 语法、Schema、引用、覆盖校验。
4. `exporters`: screenplay YAML 导出和导出后回读校验。
5. `generation`: 分阶段编排、确定性组装、`FakeLLMClient` 和 `PipelineFailure`。
6. `apps/api`: 本地 FastAPI MVP 入口，提供项目、章节确认、同步生成、job 查询和 artifacts 查询。

生成链路：

```text
uploaded chapters
  -> user rights confirmation
  -> chapter confirmation
  -> chapter summaries and key events
  -> scene plan
  -> scene content blocks
  -> backend ScreenplayDraftDocument
  -> YAML export
  -> YAML re-parse validation
  -> ValidationReport
  -> API artifacts
```

## P0a-lite-1 明确边界

- API 使用内存存储，不使用数据库。
- 生成端点同步执行，不引入异步任务队列。
- 默认 LLM 为 `FakeLLMClient`，用于本地演示和测试。
- API 不对源文本做 prompt-injection 清洗；源文本作为不可信数据传入 generation 层，由 prompt 边界、DTO、字段白名单和校验层处理。
- 章节列表不返回原文，只返回 `char_count`。
- 少于 3 章不能进入生成闭环。

## P0a-lite-2：作者编辑闭环

已开始补充：

1. YAML re-import validation endpoint: `POST /screenplays/validate-yaml`。
2. 作者编辑指南: `docs/AUTHOR_EDITING_GUIDE.md` 和打包 `schema.md`。
3. `adaptation_changes` 编辑语义: source chapter、affected scene 和 omitted key-event 规则。
4. 更严格的章节覆盖和 key-event 覆盖验证。
5. 生成前成本和风险提示: `GET /projects/{project_id}/generation-notice`。

仍需后续补充：

1. 作者编辑后的 YAML 持久化/版本管理。
2. 删除支持和更明确的数据生命周期控制。
3. 前端编辑器或更完整的作者工作台。

## 更后续阶段

### P0a

- 基础角色抽取。
- 基础地点抽取。
- 时间线抽取。
- Story Bible 草稿。
- 更完整的 validation report。

### P0b

恢复链(已实现):

- 场景级局部重生成(已实现):`POST /screenplays/{id}/scenes/regenerate`,只重写指定场景并产出新 screenplay,保留原 screenplay。
- failed-stage recovery(已实现):生成管线缓存各阶段中间产物;`POST /jobs/{id}/retry` 从失败阶段恢复重试,跳过已完成阶段,不重复调用 LLM。

尚未实现:

- 更细粒度 `source_refs`。
- generation report。
- 更强自动引用修复。
