# API 契约

本 API 是 P0a-lite 的本地 MVP 后端入口。当前实现不包含鉴权、持久化数据库或异步队列；所有项目、任务和成品均保存在进程内存中。

## 通用约定

- Base URL: 本地运行的 FastAPI 服务，例如 `http://127.0.0.1:8000`
- 请求/响应格式: JSON
- 上传小说文本前必须确认拥有改编/使用权。
- 章节列表接口只返回 `char_count`，不返回源文本。
- 生成流程同步执行；`job` 会在响应时立即进入终态。
- 默认 LLM provider 是 `FakeLLMClient`。设置 `NOVEL_TO_SCREENPLAY_LLM_PROVIDER=openai` 后，会使用 OpenAI-compatible provider，并读取 `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_BASE_URL`、`OPENAI_TIMEOUT_SECONDS` 和 `OPENAI_MAX_RETRIES`。

## POST /projects

创建项目并上传章节文本。

### Request

```json
{
  "title": "小说标题",
  "original_author": "作者",
  "language": "zh",
  "rights_confirmed": true,
  "chapters": [
    {"title": "第一章", "text": "章节正文"},
    {"title": "第二章", "text": "章节正文"},
    {"title": "第三章", "text": "章节正文"}
  ]
}
```

### Response 201

```json
{
  "project_id": "proj-...",
  "title": "小说标题",
  "original_author": "作者",
  "language": "zh",
  "chapter_count": 3,
  "chapters_confirmed": false
}
```

### Errors

- `403`: `rights_confirmed` 不是 `true`。

## GET /projects/{project_id}/chapters

返回项目章节清单，不返回章节源文本。

### Response 200

```json
{
  "project_id": "proj-...",
  "chapters": [
    {
      "chapter_id": "ch-1",
      "order": 1,
      "title": "第一章",
      "char_count": 1234,
      "confirmed": false
    }
  ]
}
```

### Errors

- `404`: 项目不存在。

## POST /projects/{project_id}/chapters/confirm

确认章节解析结果。当前实现为幂等操作。

### Response 200

```json
{
  "project_id": "proj-...",
  "chapters_confirmed": true,
  "chapter_count": 3
}
```

### Errors

- `404`: 项目不存在。

## GET /projects/{project_id}/generation-notice

返回生成前成本与风险提示。该接口不调用 LLM。

### Response 200

```json
{
  "project_id": "proj-...",
  "chapter_count": 3,
  "total_char_count": 12000,
  "estimated_scene_count": 6,
  "cost_notice": "Cost depends on provider pricing, chapter length, retry count, and the number of generated scenes; this local MVP does not estimate currency cost.",
  "risk_notice": [
    "Generation sends chapter text to the configured LLM provider.",
    "Source text is treated as untrusted data, but model output can still require author review.",
    "Large chapters can increase latency and provider cost."
  ]
}
```

### Errors

- `404`: 项目不存在。

## POST /screenplays/generate

同步执行生成流程：章节摘要、场景规划、场景正文、后端组装、校验、YAML 导出和导出后回读校验。

### Request

```json
{
  "project_id": "proj-...",
  "model": "fake-model",
  "adaptation_config": {
    "output_language": "zh",
    "target_medium": "screenplay",
    "adaptation_degree": "balanced"
  }
}
```

`adaptation_config` 可为 `null` 或省略。

### Response 201: succeeded

```json
{
  "job_id": "job-...",
  "status": "succeeded",
  "project_id": "proj-...",
  "screenplay_id": "sp-...",
  "error": null,
  "created_at": "2026-06-07T00:00:00+00:00",
  "updated_at": "2026-06-07T00:00:01+00:00"
}
```

### Response 201: failed

Pipeline 失败会保存为失败 job，并在响应中返回 `PipelineError`。

```json
{
  "job_id": "job-...",
  "status": "failed",
  "project_id": "proj-...",
  "screenplay_id": null,
  "error": {
    "failed_stage": "chapter_parsing",
    "error_type": "chapter_count_insufficient",
    "error_message": "At least three confirmed chapters are required.",
    "retryable": false,
    "completed_artifacts": [],
    "suggested_action": "Provide three or more confirmed chapters before generation."
  }
}
```

### Errors

- `404`: 项目不存在。
- `409`: 项目章节尚未确认。

## POST /screenplays/validate-yaml

作者编辑 YAML 后，重新上传并运行语法、Schema、引用和覆盖校验。该接口不存储传入 YAML。

### Request

```json
{
  "yaml": "metadata:\n  ..."
}
```

### Response 200

无论 YAML 是否通过校验，接口都会返回 `ValidationReport`：

```json
{
  "yaml_parse_passed": true,
  "schema_validation_passed": true,
  "reference_validation_passed": true,
  "coverage_validation_passed": true,
  "errors": [],
  "warnings": [],
  "suggested_fixes": []
}
```

## GET /jobs/{job_id}

查询同步生成 job 的终态。

### Response 200

```json
{
  "job_id": "job-...",
  "status": "succeeded",
  "project_id": "proj-...",
  "screenplay_id": "sp-...",
  "error": null,
  "created_at": "2026-06-07T00:00:00+00:00",
  "updated_at": "2026-06-07T00:00:01+00:00"
}
```

### Errors

- `404`: job 不存在。

## POST /jobs/{job_id}/retry

对失败的 job 从已完成阶段恢复重试。生成管线会缓存每个阶段的中间产物
（章节摘要、场景规划、场景正文）；重试时已完成的阶段直接复用缓存，不再调用
LLM，只重跑失败处及其后续阶段。本接口无请求体，同步执行。

### Response 200

返回更新后的 `JobResponse`。重试成功时 `status` 变为 `succeeded` 并带上新的
`screenplay_id`；若再次失败，则保持 `failed` 并刷新 `error` 与缓存产物，可继续重试。

```json
{
  "job_id": "job-...",
  "status": "succeeded",
  "project_id": "proj-...",
  "screenplay_id": "sp-...",
  "error": null,
  "created_at": "2026-06-07T00:00:00+00:00",
  "updated_at": "2026-06-07T00:00:05+00:00"
}
```

### Errors

- `404`: job 不存在。
- `409`: job 当前状态不是 `failed`（只有失败的 job 可重试）。
- `409`: `error.retryable` 为 `false`（`detail` 为该错误的 `suggested_action`）。
- `409`: 关联项目已不存在，无法重建生成输入。

## GET /screenplays/{screenplay_id}/artifacts

返回生成产物。

### Response 200

```json
{
  "screenplay_id": "sp-...",
  "yaml": "metadata:\n  ...",
  "document": {},
  "validation_report": {}
}
```

`document` 是 `shared_types.ScreenplayDraftDocument` 的 JSON 结构；`validation_report` 是导出 YAML 回读后的 `ValidationReport`。

### Errors

- `404`: screenplay 不存在。

## POST /screenplays/{screenplay_id}/scenes/regenerate

对已生成的剧本只重写指定场景。复用缓存的章节摘要与场景规划，仅对目标场景调用一次
LLM，其余场景正文原样保留，然后确定性地重新组装、校验并导出。结果是一个**全新的
screenplay（新 `screenplay_id`），原 screenplay 保留**以便对比与回滚。`model` 与
`adaptation_config` 沿用原 screenplay 元数据。本接口同步执行。

### Request

```json
{
  "scene_id": "sc-001"
}
```

`scene_id` 必须形如 `sc-NNN`（三位数字）。

### Response 201

返回新 screenplay 的 `ArtifactsResponse`（结构同 `GET /artifacts`）。

```json
{
  "screenplay_id": "sp-...",
  "yaml": "metadata:\n  ...",
  "document": {},
  "validation_report": {}
}
```

### Errors

- `404`: screenplay 不存在。
- `404`: `scene_id` 在场景规划中不存在或格式不合法。
- `409`: 关联项目已不存在，或重生成后的组装/校验/导出失败。

## GET /screenplays/{screenplay_id}/validation-report

返回已生成 screenplay 的校验报告。

### Response 200

```json
{
  "yaml_parse_passed": true,
  "schema_validation_passed": true,
  "reference_validation_passed": true,
  "coverage_validation_passed": true,
  "errors": [],
  "warnings": [],
  "suggested_fixes": []
}
```

### Errors

- `404`: screenplay 不存在。

## GET /screenplays/{screenplay_id}/schema-doc

返回当前打包的 `schema.md` 文档，供作者编辑 YAML 时查看字段语义。

### Response 200

```json
{
  "schema_filename": "schema.md",
  "schema_doc": "# Screenplay YAML Schema\n..."
}
```

### Errors

- `404`: screenplay 不存在。
