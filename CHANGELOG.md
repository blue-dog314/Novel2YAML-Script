# Changelog

本项目所有重要变更都记录在此文件。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 暂无

## [0.1.0] - 2026-06-06

P0a-lite-1 后端闭环骨架:从 3+ 章小说文本到结构化对象、YAML 导出、Schema 校验与校验报告。

### Added
- 初始化 uv workspace monorepo 脚手架（`apps/`、`packages/`、`docs`、根 smoke 测试）。
- `shared_types` 契约层：模型输出 DTO、后端文档模型、校验报告、`ValidatedScreenplay` 品牌类型、`PipelineError` 失败契约；全量 `extra="forbid"` 字段白名单防御。
- `screenplay_schema`：从契约层生成 JSON Schema，打包静态 `screenplay.schema.json` 与版本化 `schema.md`。
- `validators`：四层确定性校验（语法、Schema、引用、覆盖）。
- `exporters`：作者友好的 YAML 导出，并在导出后回读校验（`export_validated_yaml`）。
- `generation`：分阶段编排（章节摘要 → 场景规划 → 场景写作 → 确定性组装 → 校验 → 导出），含 `FakeLLMClient` 确定性测试桩与 `PipelineFailure` 失败处理。

### Docs
- 补充项目契约、MVP 计划与评审文档。
- 补充 PR 提交规范。

### Chore
- 忽略本地打包产物。

[Unreleased]: https://github.com/blue-dog314/Novel2YAML-Script/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/blue-dog314/Novel2YAML-Script/releases/tag/v0.1.0
