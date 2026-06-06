# API 契约

本 API 是 P0a-lite-1 的本地 MVP 后端入口。当前实现不包含鉴权、持久化数据库或异步队列；所有项目、任务和成品均保存在进程内存中。

## 通用约定

- Base URL: 本地运行的 FastAPI 服务，例如 `http://127.0.0.1:8000`
- 请求/响应格式: JSON
- 上传小说文本前必须确认拥有改编/使用权。
- 章节列表接口只返回 `char_count`，不返回源文本。
- 生成流程同步执行；`job` 会在响应时立即进入终态。

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
  "error": null
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

## GET /jobs/{job_id}

查询同步生成 job 的终态。

### Response 200

```json
{
  "job_id": "job-...",
  "status": "succeeded",
  "project_id": "proj-...",
  "screenplay_id": "sp-...",
  "error": null
}
```

### Errors

- `404`: job 不存在。

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
