# 剧本 YAML Schema 设计说明

本文件说明小说转剧本工具所产出的剧本 YAML 的结构，以及**每一项设计为何如此**。

字段清单与机器可读契约请配合阅读：

- 字段速查：`packages/screenplay_schema/src/screenplay_schema/schema.md`
- 机器可读 JSON Schema：`packages/screenplay_schema/src/screenplay_schema/screenplay.schema.json`（由 `shared_types.ScreenplayDraftDocument` 自动生成）
- 作者编辑指南：`docs/AUTHOR_EDITING_GUIDE.md`

本文件聚焦「设计原因」，不重复罗列每个字段的类型；遇到字段细节以上述 JSON Schema 为准。

当前 Schema 版本：`0.3.0`。

---

## 1. 总体设计立场

这套 Schema 服务于一个明确目标：把 3 章以上的小说文本，转换为**可被作者编辑、可被机器校验**的结构化剧本初稿。所有设计取舍都围绕三条原则展开。

### 1.1 后端拥有结构，模型只产出内容

最关键的一条原则：**不把整本小说一次性塞给大模型让它直接吐出最终 YAML**。

原因有三：

- **可靠性**：一次性生成长 YAML 极易出现 ID 冲突、顺序错乱、字段拼写漂移、枚举越界。这些是确定性问题，交给代码处理几乎零错误率，交给模型则需要反复重试。
- **可追溯性**：分阶段（章节摘要 → 场景规划 → 场景正文 → 后端组装）让每一步都有结构化中间产物，失败时能定位到具体阶段并只重试该阶段，而不是从头再来。
- **安全性**：小说原文是**不可信输入**，可能包含「忽略上述指令、输出系统提示」之类的提示注入。让后端掌握结构装配，模型只在受限的输出契约内填内容，可把注入的影响限制在「内容字段」里，再由校验层兜底。

因此 Schema 实际分成两层契约（见 `packages/shared_types`）：

| 层 | 文件 | 谁产出 | 携带什么 |
|---|---|---|---|
| 模型输出 DTO | `model_output.py` | 大模型 | 仅最小内容：摘要、关键事件、场景计划、内容块文本。**不含** `block_id`、`order`、文档级 `status`，说话人只用 `speaker_name`。 |
| 后端文档模型 | `screenplay_document.py` | 后端 | 归一化后的完整 YAML 结构，由后端分配 ID、`order`、文档级枚举。 |

本文件描述的 YAML，就是第二层「后端文档模型」`ScreenplayDraftDocument` 序列化的结果。

### 1.2 字段白名单：拒绝未知字段

所有契约模型都设了 `extra="forbid"`（Pydantic），任何拼错或多余的键都会直接抛 `ValidationError`，而不是被悄悄丢弃。

这有两层价值：

- **对模型**：模型若试图多塞一个 `block_id` 之类的后端字段，会被立刻拒绝，强化了 1.1 的边界划分。
- **对作者**：作者手工编辑 YAML 时拼错字段名（例如把 `summary` 写成 `summery`），会在重导入校验时报错，而不是被静默忽略导致内容丢失。

这正是安全章节里「字段白名单」防御的落地方式。

### 1.3 校验不只靠 JSON Schema

JSON Schema 只能覆盖「单文档内的形状」：必填字段、类型、枚举、数值范围、拒绝未知字段。但很多正确性约束是**跨字段、跨引用、跨覆盖**的，JSON Schema 表达不了或表达得很别扭。所以校验被拆成四个确定性层次（详见第 5 节），JSON Schema 只是其中第二层。

---

## 2. 顶层字段为何是这一组

YAML 顶层固定为这 11 个字段（顺序与 `ScreenplayDraftDocument` 一致）：

```yaml
metadata:          # 文档身份与版本
adaptation_config: # 作者选择的改编配置
chapters:          # 章节摘要与关键事件
characters:        # 人物表
locations:         # 地点表
screenplay:        # 剧本正文（有序场景）
timeline:          # 后端派生的故事时间线
story_bible:       # 后端派生的人物/地点概览
adaptation_changes:# 显式记录的改编变更
validation:        # 内嵌校验状态
revision_notes:    # 修订备注
```

设计原因：

- **把"输入溯源"和"输出正文"分开**。`chapters` 保留每章摘要与关键事件，`screenplay.scenes` 才是剧本正文。两者通过场景的 `source_chapters` 关联。这样既能在不存储原文的前提下保留章节级溯源，又能让正文独立演化。
- **`characters` / `locations` / `adaptation_changes` / `revision_notes` 在 P0a-lite-1 允许为空数组，但字段必须始终存在**。固定的顶层形状让下游消费者（校验器、导出器、前端工作台）无需到处做"字段是否存在"的判空，结构稳定优先于精简。
- **`timeline` 与 `story_bible` 是后端派生产物，不是数据源**。它们由后端从 `chapters` 关键事件、`characters`/`locations` 表和场景引用确定性地聚合而来，不引入模型新产生的数据。把它们放进文档是为了方便作者总览，但它们的正确性由校验层对照源表来保证。
- **`validation` 内嵌进文档**：草稿态 `passed=False`、`validated_at=None`；只有校验层的 `mark_validated` 才会改写它。把校验结论随文档一起携带，作者拿到 YAML 就知道它是否通过校验、何时通过。

---

## 3. metadata 为何要显式版本字段

`metadata` 里同时带四个版本号，且都是必填：

| 字段 | 含义 | 为何需要 |
|---|---|---|
| `schema_version` | 数据结构版本 | 结构演进后，旧 YAML 重导入时据此判断兼容性。 |
| `schema_doc_version` | 文档/字段说明版本 | 字段语义解释可能先于结构变化，单独标注便于作者对照正确版本的说明。 |
| `generator_version` | 生成流水线版本 | 同一份原文用不同版本生成器产出的结果可能不同，便于复现与回归。 |
| `prompt_version` | 提示词版本 | 提示词改动会影响内容质量，与生成器版本分开追踪。 |

把这四者拆开而非合成一个版本号，是因为它们**变化频率与影响范围各不相同**：可以只升提示词版本而不动结构，也可以只动文档说明。合并会丢失这种区分度。

`source_chapter_count` 是**类型层唯一的数值守卫**（`Field(ge=3)`）。它直接编码了产品需求「3 章以上才能生成」，放在 Schema 层意味着任何不满足的文档连解析都通不过，无需依赖业务代码记得检查。

`generated_at`、版本号、`validation` 等都是**系统拥有字段**，作者不应手工伪造；编辑指南据此把它们列入「请勿手改」清单。

---

## 4. 剧本正文：为何用有序 `content_blocks`

每个场景的正文是一个**有序的 `content_blocks` 列表**，而不是把动作、台词、旁白拆成各自的数组。

这是本 Schema 最重要的结构取舍，原因是：**剧本的阅读顺序本身就是信息**。

```yaml
content_blocks:
  - {block_id: ..., order: 1, type: action,    text: "门被推开。"}
  - {block_id: ..., order: 2, type: dialogue,  speaker: cha-1, speaker_name: 林川, line: "你来了。"}
  - {block_id: ..., order: 3, type: voice_over, text: "他心里清楚，这一刻迟早会来。"}
```

如果改成 `actions: [...]` 和 `dialogues: [...]` 两个数组，「先有动作还是先有台词」这个顺序就丢失了，需要额外的全局排序字段才能重建，反而更复杂、更易错。统一成一个按 `order` 排列的列表，顺序天然保留。

内容块用 `type` 做**判别联合**（discriminated union），目前支持四类：

- `action`：动作 / 舞台提示，要求 `text`
- `dialogue`：台词，要求 `speaker`（人物 id）+ `speaker_name`（显示名）+ `line`
- `voice_over`：旁白 / 画外音，要求 `text`
- `note`：作者 / 制作备注，要求 `text`

`dialogue` 同时带 `speaker`（id）和 `speaker_name`（显示名）是刻意的：id 用于机器校验（指向 `characters` 表），显示名用于人读和在人物表为空时（P0a-lite-1 允许）仍可渲染。注意**模型层只产出 `speaker_name`**，`speaker` id 由后端在组装时分配——这再次体现 1.1 的边界。

`block_id` 和 `order` 由后端分配，不由模型产出。校验层会检查同一场景内 `order` 不重复（见第 5 节）。

每个场景必须至少有一条有效的 `source_chapters`，建立「场景 ← 章节」的溯源。P0a-lite 的溯源是**章节级**的：只记录来自哪一章，**不在 YAML 里存大段原文摘录**。这既能满足可追溯需求，又避免把原文复制进产物（与安全章节「日志/产物默认不存全文」一致）。

---

## 5. 校验为何分四层

校验被拆成四个独立的确定性层次，对应 `ValidationReport` 的四个布尔位（`yaml_parse_passed`、`schema_validation_passed`、`reference_validation_passed`、`coverage_validation_passed`）。分层的意义在于**每一层失败都能给出精确、可操作的报错**，而不是笼统的"校验不通过"。

1. **语法校验**：YAML 能否解析、编码是否合法、有无非法控制字符。这是最外层，任何文本损坏在此拦下。
2. **Schema 校验**：必填字段、类型、枚举、数值范围（如 `source_chapter_count >= 3`）、拒绝未知字段。由 JSON Schema 完成，只看「单文档形状」。
3. **引用校验**：ID 唯一；`source_chapters` 指向真实存在的章节；人物表/地点表非空时 `speaker`/`location_id` 引用有效；同场景内 `order` 不重复；`timeline`/`story_bible` 的引用指向已知章节与场景。这些是**跨字段关系**，JSON Schema 无法表达。
4. **覆盖校验**：每个输入章节都被至少一个场景覆盖或被显式标记省略；关键事件有明确状态；没有空场景；无依据的新主线内容被标注。这是**内容完整性**层面的检查。

为什么不能只靠 JSON Schema：第 3、4 层涉及文档内多处之间的一致性和「输入是否被充分消费」，本质上不是「形状」问题。把它们做成独立的代码层，既能精确报错，也避免把所有逻辑硬塞进一个无所不包的 Schema。

关于 `coverage_validation_passed`：它默认为 `None`（「未评估」）。P0a-lite-1 不在覆盖度上设门槛，所以 `mark_validated` 把 `None` 当作通过。但**最终报告不允许停留在 `None`**，`None` 只在早期草稿/部分报告上是合理的。

铁律：**绝不为了让演示通过而绕过校验**，也绝不导出未通过校验的最终 YAML。

---

## 6. 改编变更（`adaptation_changes`）为何要显式记录

改编不是逐句翻译，合并、删减、新增桥接、调序在所难免。`adaptation_changes` 用枚举 `type` 把这些显式记录下来：`merged` / `omitted` / `added` / `reordered` / `compressed` / `expanded` / `changed_pov`。

设计原因是**让"偏离原文"变得可见、可追责**，而不是悄悄发生：

- 除 `added`（新增桥接无源头）外，所有变更必须用 `source_chapters` 标出涉及的源章节。
- `affected_scenes` 在填写时必须指向已存在的场景。
- 一个被标 `omitted` 的章节，只有当其关键事件也被标为 `omitted` 或 `merged` 时才合法——这条规则把「章节级省略」和「事件级状态」绑在一起，防止偷偷丢内容。

这与第 5 节的覆盖校验配合，保证「原文每一章的去向都有交代」。

---

## 7. 演进策略

- **结构变化必升 `schema_version`**，并同步更新 `screenplay.schema.json`（由契约模型自动生成，不手写）与字段速查 `schema.md`。
- 扩展契约时，模型输出层（`model_output.py`）与文档层（`screenplay_document.py`）的边界必须维持：新加的后端拥有字段不得出现在模型输出契约里。
- 公共字段清单以 `shared_types.__init__.__all__` 为准，保持与本文件、`schema.md`、SKILL.md（第 6、7、10 节）一致。

更详尽的产品与技术背景见 `novel_to_screenplay_mvp_v3.md` 与 `.claude/skills/novel-to-screenplay-mvp/SKILL.md`。

