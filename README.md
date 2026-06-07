# Novel2YAML-Script

AI 辅助的「小说 → 结构化剧本 YAML」工具(P0a-lite MVP)。把 3 章以上的小说原文,经过分阶段生成流水线,转换为可编辑、经 Schema 校验的剧本 YAML 草稿。

本仓库是基于 [uv](https://docs.astral.sh/uv/) workspace 的 Python monorepo,内含后端契约层、校验层、生成编排、YAML 导出层,以及一个本地 FastAPI 演示 API 与内嵌的「作者工作台」单页前端。

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)(workspace 与依赖管理)

## 快速开始

```bash
uv sync                                   # 安装全部依赖
uv run pytest                             # 运行全量测试
uv run mypy .                             # strict 类型检查
uv run uvicorn api.app:app --reload       # 启动 API 与 /app 工作台
```

启动后访问 `http://127.0.0.1:8000/app` 使用作者工作台;API 文档见 `docs/API.md`。

## 第三方依赖

### 运行时(Python)

| 依赖 | 版本约束 | 用途 | 使用方 |
| --- | --- | --- | --- |
| [pydantic](https://docs.pydantic.dev/) | `>=2.0` | 契约层数据模型(`extra="forbid"` 字段白名单) | `shared_types` |
| [ruamel.yaml](https://yaml.readthedocs.io/) | `>=0.18` | YAML 序列化与解析校验 | `exporters`、`validators` |
| [fastapi](https://fastapi.tiangolo.com/) | `>=0.115` | 本地演示 API | `apps/api` |
| [uvicorn](https://www.uvicorn.org/) | `>=0.30` | ASGI 服务器 | `apps/api` |

### 开发期(Python)

| 依赖 | 版本约束 | 用途 |
| --- | --- | --- |
| [pytest](https://docs.pytest.org/) | `>=8.0` | 测试框架 |
| [mypy](https://mypy.readthedocs.io/) | `>=1.10` | strict 静态类型检查 |
| [httpx](https://www.python-httpx.org/) | `>=0.27` | FastAPI TestClient 依赖 |

构建后端统一使用 [hatchling](https://hatch.pypa.io/)。

### 前端(已 vendor,随仓库分发,无需构建步骤)

| 依赖 | 版本 | 用途 | 路径 |
| --- | --- | --- | --- |
| [Vue 3](https://vuejs.org/) | 3.5.35 | 工作台单页交互(免构建全局版) | `apps/api/src/api/static/vendor/vue.global.js` |
| [Pico CSS](https://picocss.com/) | 2.1.1 | 工作台样式 | `apps/api/src/api/static/vendor/pico.min.css` |

工作台仅以原生 `fetch` 调用同源 API,不引入打包器或 npm 依赖。

## 原创功能说明

除上述第三方库外,以下能力为本项目原创实现:

- **分阶段生成流水线(`packages/generation`)**:章节摘要 → 关键事件 → 分场规划 → 场景内容块 → 后端装配,每一阶段产出受约束的结构化中间产物,而非「整本小说一次成稿」。失败处理遵循「同阶段至多自动修复一次、保留已完成中间产物、绝不导出非法 YAML」。
- **后端确定性装配(`assembly.py`)**:ID 分配、`order` 分配、枚举归一化、角色/地点去重、key-event 确定性 ID(`{chapter_id}-ev-{index:03d}`)全部由后端拥有;模型输出被视为不可信,只提供名称与文本。
- **分层确定性校验(`packages/validators`)**:语法、Schema、引用、覆盖(含章级与 key-event 级覆盖)四层独立校验,产出可读的 `validation_report`,绝不为通过演示而绕过校验。
- **YAML 导出与回环校验(`packages/exporters`)**:后端拥有序列化,导出后再次校验,多行文本以块标量输出。
- **契约层双模型(`packages/shared_types`)**:模型输出 DTO 与后端文档模型严格分离,全字段白名单(`extra="forbid"`)作为提示注入防御的一环。
- **JSON Schema 与静态文档(`packages/screenplay_schema`)**:既生成 JSON Schema,也提供带版本的静态 `schema.md`。
- **本地作者工作台(`apps/api`)**:免构建单页前端驱动「上传确权 → 章节确认 → 生成 → 校验报告 → 产物下载」完整闭环。

## 安全与版权约束

- 接收上传原文前要求用户确认拥有改编/使用权利。
- 小说原文一律按不可信数据处理,通过分隔符、提示边界、结构化输出契约、字段白名单、Schema 不可变与导出前校验等多重手段防御提示注入。
- 日志默认不存储完整原文;原文、生成结果与日志分离存储,支持删除。

## 仓库结构

```text
apps/
  api/                 # FastAPI 本地 MVP API + 内嵌 /app 工作台(src/api/static)
packages/
  shared_types/        # 跨层契约(Pydantic 模型)
  screenplay_schema/   # JSON Schema 与静态 schema 文档
  validators/          # 分层确定性校验
  generation/          # 分阶段生成编排
  exporters/           # YAML 导出与回环校验
docs/                  # API、MVP、安全、测试文档
tests/                 # 根 smoke 测试
```

依赖方向:`shared_types` → `screenplay_schema`/`validators` → `exporters`/`generation` → `apps/api`(下层不得反向依赖上层)。

## 构建分发

```bash
uv build --all-packages      # 构建全部 workspace 成员
```

不要在仓库根运行裸 `uv build`:workspace 根 `package = false`,裸构建会因 setuptools flat-layout 报错,这是预期行为。
