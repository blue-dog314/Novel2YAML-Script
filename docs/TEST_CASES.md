# 测试用例

本文档记录 P0a-lite 当前验收测试重点。实际自动化测试以 `pytest` 为准。

## 验证命令

```bash
uv sync
uv run pytest
uv run mypy .
uv build --all-packages
```

针对 API 可单独运行：

```bash
uv run pytest apps/api
uv run mypy apps/api/src apps/api/tests
```

## 根与包级 smoke tests

- 根 smoke test 能导入 workspace 包。
- 每个包保留 import smoke test。
- `MODULE_NAME` public surface 保持兼容。

## shared_types

覆盖重点：

- Pydantic models 全量 `extra="forbid"`。
- 模型输出 DTO 不包含 backend-owned 字段。
- backend document 包含稳定 ID、order 和 document-level enum。
- `ContentBlock` 使用 `type` discriminated union。
- `ValidationReport.errors` 只能包含 error-severity issue。
- `ValidatedScreenplay` 只能通过 validators internal boundary mint。
- `PipelineError` 包含失败阶段、错误类型、用户可读消息、retryable、已完成 artifacts 和建议动作。

## screenplay_schema

覆盖重点：

- 能从 `ScreenplayDraftDocument` 生成 JSON Schema。
- schema 包含 P0a-lite 顶层字段。
- 打包静态 `screenplay.schema.json`。
- 打包/提供版本化 `schema.md`。

## validators

覆盖重点：

- YAML 语法错误会返回 parse failure。
- 非法控制字符会失败。
- Pydantic schema validation 会报告字段、类型、enum 错误。
- 引用校验覆盖重复 ID、重复 order、未知 source chapter、未知 speaker/location。
- 引用校验覆盖 `adaptation_changes[].source_chapters` 和 `adaptation_changes[].affected_scenes`。
- 覆盖校验覆盖空章节、空场景、空 content_blocks、章节未覆盖、空 key events、被 omitted 章节仍保留 active key events。
- final report 不应让 `coverage_validation_passed` 保持 `None`。

## exporters

覆盖重点：

- YAML 导出保留字段顺序和 unicode。
- `None` 输出为 `null`。
- 导出后可重新 parse。
- `export_validated_yaml` 只返回通过 validators 的 YAML 和 report。

## generation

覆盖重点：

- 少于 3 章在入口失败，不调用 LLM。
- 按阶段调用：summarizing、scene_planning、scene_content_generation。
- 自动 repair 同阶段最多一次。
- repair 失败时抛出 `PipelineFailure`。
- 失败时保留 `completed_artifacts`。
- 组装层负责 ID、order、speaker slug 和 YAML document 字段。
- 生成结果通过 validate 和 export revalidation。
- prompt 明确把源文本标记为 untrusted data，并使用边界分隔。
- OpenAI-compatible LLM client 通过环境变量读取 key/model/base URL/timeout/retry 配置。
- OpenAI-compatible LLM client 使用 chat completions JSON response format，并对临时网络错误重试。

## apps/api

覆盖重点：

- `POST /projects` 在 `rights_confirmed != true` 时返回 403。
- `GET /projects/{id}/chapters` 不返回 `text`，只返回 `char_count`。
- `POST /projects/{id}/chapters/confirm` 幂等。
- 未确认章节时调用 generate 返回 409。
- 不存在的 project/job/screenplay 返回 404。
- happy path 生成 job 成功，并可查询 artifacts。
- `GET /projects/{id}/generation-notice` 返回生成前成本与风险提示。
- `POST /screenplays/validate-yaml` 可重新校验作者编辑后的 YAML。
- `GET /screenplays/{id}/validation-report` 返回已生成 screenplay 的校验报告。
- `GET /screenplays/{id}/schema-doc` 返回打包的 `schema.md`。
- 少于 3 章生成返回 failed job，错误类型为 `chapter_count_insufficient`。
- pipeline 中间阶段失败返回 failed job 和 `PipelineError`。
- prompt-injection 文本原样作为不可信 payload 传入 generation prompt，不由 API 当作指令处理。

## 当前基线

最近一次本地验证结果：

- `uv run pytest apps/api`: 13 passed。
- `uv run pytest`: 117 passed。
- `uv run mypy .`: no issues。
- `uv build --all-packages`: 成功。
