# Scaffold / 契约层 Review 建议

## Review 范围

本次 review 覆盖项目主目录规格材料，以及 `.claude/worktrees/agent-a7a17cbb` 中已生成的 scaffold。

当前判断：项目主目录仍主要是规格包；实际 scaffold 位于 `.claude/worktrees/agent-a7a17cbb`，且契约层仍是占位状态。

## 总体结论

这个模块目前已经有 monorepo 目录形状，但还不能算可用的 Scaffold / 契约层。最核心的问题是：schema、types、validators、exporter、API contract 没有形成同一份可执行契约。

建议下一步优先把 P0a-lite-1 的最小工程闭环打通：

```text
shared types
  -> screenplay.schema.json
  -> YAML exporter
  -> YAML parse validation
  -> JSON Schema validation
  -> reference validation
  -> basic validation_report
```

## P1 必须修复

### 1. Scaffold 不在项目主目录

现状：

- 主目录仍只有规格文件和 skill 包。
- 实际 scaffold 在 `.claude/worktrees/agent-a7a17cbb`。
- 主目录的 `CLAUDE.md` 仍描述为“没有 README、package manifest、build system、test framework”。

风险：

- 用户在主目录执行 `pnpm test`、`pnpm typecheck` 会失败。
- 后续开发者可能不知道真实 scaffold 在哪里。
- 交付物边界不清晰。

建议：

- 如果 `.claude/worktrees/agent-a7a17cbb` 是目标 scaffold，应迁移到主目录。
- 如果它只是 agent 临时产物，应在主目录重新生成正式 scaffold。
- 主目录应包含 `package.json`、`pnpm-workspace.yaml`、`tsconfig.json`、`vitest.config.ts`、`apps/`、`packages/`、`docs/`。

### 2. 契约包目前是空壳

现状：

- `packages/screenplay-schema/src/index.ts` 只导出模块名常量。
- `packages/validators/src/index.ts` 只导出模块名常量。
- `packages/exporters/src/index.ts` 只导出模块名常量。
- `apps/api/src/index.ts` 也只导出模块名常量。

风险：

- 规格中的 YAML 结构没有被机器约束。
- 生成、导出、验证、API 可能各自实现一套字段。
- 后续容易发生 schema drift。

建议：

- `shared-types` 先定义核心 domain types。
- `screenplay-schema` 提供 `screenplay.schema.json` 和 schema version。
- `validators` 拆出 syntax/schema/reference/coverage validator。
- `exporters` 提供对象到 YAML 的稳定序列化，并 parse back 验证。
- `api` 先提供 request/response/error contract，即使暂不实现 HTTP server。

### 3. 模型输出契约和最终 YAML 契约不一致

现状：

- 最终 `chapters[].key_events[]` 要求 `status`，但模型输出示例使用 `importance`。
- 最终 `content_blocks[]` 要求 `block_id`、`order`、`type`，但模型输出示例没有 `block_id/order`。
- 最终 dialogue block 要求 `speaker`、`speaker_name`、`line`，但模型输出示例只有 `speaker_name` 和 `line`。

风险：

- 后端需要隐式补字段，补字段规则如果不明确会导致不可预测行为。
- validator 会把合法模型输出判为非法，或被迫放松最终 schema。
- repair 阶段可能频繁触发，增加成本和失败率。

建议：

- 明确拆分两层契约：
  - `ModelOutputDTO`：模型允许输出的最小结构。
  - `ScreenplayDocument`：后端规范化后的最终 YAML/domain 结构。
- 后端 normalization 明确负责：
  - 分配 `event_id`、`scene_id`、`block_id`。
  - 分配 `order`。
  - 将 `importance` 转为内部参考信息，或移除。
  - 将 `speaker_name` 解析/映射为 `speaker`，无法映射时生成 warning 或 pending review。
- 不允许模型直接产出最终 YAML。

### 4. P0a-lite-1 的 coverage validation 口径冲突

现状：

- 总流程写了 reference and coverage validation。
- P0a-lite-1 列到 reference validation 和 basic validation_report。
- P0a-lite-2 才加入 chapter coverage validation 和 key-event coverage validation。
- 验收标准又要求每个输入章节都 covered 或 omitted。

风险：

- validator 不知道 P0a-lite-1 是否应该因为 coverage 不完整而失败。
- API 返回的 validation report 语义不稳定。
- 测试用例无法确定 expected result。

建议：

- P0a-lite-1 最小 gate：
  - `source_chapter_count >= 3`
  - 每个 scene 至少一个有效 `source_chapters`
  - 每个 scene 的 `content_blocks` 非空
  - 每个 scene 至少包含一个 action 或 dialogue block
  - scene/chapter/block order 不重复
- P0a-lite-2 再 gate：
  - 每个输入章节被 scene 覆盖或在 `adaptation_changes` 中标记 omitted
  - key events 有 status
  - 新增主线剧情必须有 `adaptation_changes` 或 `adaptation_notes`

## P2 优化建议

### 1. 补 API contract，而不是先写完整 API

建议先定义：

```ts
type CreateProjectRequest = {
  title: string;
  original_author?: string;
  source_text: string;
  rights_confirmed: boolean;
};

type CreateProjectResponse = {
  project_id: string;
  chapter_parse_status: 'parsed' | 'needs_confirmation' | 'failed';
};

type PipelineError = {
  failed_stage: string;
  error_type: string;
  error_message: string;
  retryable: boolean;
  completed_artifacts: string[];
  suggested_action: string;
};
```

优先覆盖接口：

- `POST /projects`
- `GET /projects/{project_id}/chapters`
- `POST /projects/{project_id}/chapters/confirm`
- `POST /screenplays/generate`
- `GET /jobs/{job_id}`
- `GET /screenplays/{screenplay_id}/artifacts`
- `POST /screenplays/validate-yaml`

### 2. 测试配置应覆盖 apps

现状：

- `vitest.config.ts` 只 include `packages/**/*.test.ts`。

建议：

```ts
include: ['packages/**/*.test.ts', 'apps/**/*.test.ts']
```

否则 API contract tests 不会被默认执行。

### 3. package 边界需要更明确

现状：

- 各 package 的 `package.json` 只有 `main: "./src/index.ts"`。
- 没有 `exports`、`types`、包间 dependencies。

建议：

- 给每个包补 `exports`。
- `validators` 依赖 `screenplay-schema` 和 `shared-types`。
- `exporters` 依赖 `shared-types` 和 `validators`。
- `generation` 依赖 `shared-types`，但不要依赖 final YAML exporter。
- `api` 依赖 `shared-types`、`generation`、`exporters`、`validators`。

### 4. validation_report 需要结构化类型

建议最小结构：

```ts
type ValidationReport = {
  yaml_parse_passed: boolean;
  schema_validation_passed: boolean;
  reference_validation_passed: boolean;
  coverage_validation_passed?: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  suggested_fixes: string[];
};

type ValidationIssue = {
  code: string;
  message: string;
  path?: string;
  severity: 'error' | 'warning';
};
```

## 推荐实施顺序

1. 决定 scaffold 是否迁移到项目主目录。
2. 固化 P0a-lite-1 validation gate。
3. 在 `shared-types` 中补 `ScreenplayDocument`、`Chapter`、`Scene`、`ContentBlock`、`ValidationReport`、`PipelineError`。
4. 在 `screenplay-schema` 中补 `screenplay.schema.json`。
5. 在 `validators` 中实现最小 validator：
   - YAML parse
   - JSON Schema
   - reference validation
   - P0a-lite-1 basic coverage checks
6. 在 `exporters` 中实现 YAML export + parse back + validate。
7. 在 `apps/api` 中补 route contracts。
8. 增加测试：
   - schema accepts valid sample
   - schema rejects missing required fields
   - reference validator rejects invalid `source_chapters`
   - exporter output can parse back
   - `source_chapter_count < 3` must fail
   - invalid dialogue speaker behavior is deterministic

## 最小验收标准

完成上述修复后，至少应能做到：

- `pnpm test` 可在主目录运行。
- `pnpm typecheck` 可在主目录运行。
- 有一个 sample `ScreenplayDocument` 能导出 YAML。
- 导出的 YAML 能 parse back。
- parse back 后能通过 JSON Schema。
- invalid `source_chapters` 会被 reference validator 拒绝。
- `validation_report` 能清晰说明失败原因。

