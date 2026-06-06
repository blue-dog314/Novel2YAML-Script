# 作者 YAML 编辑指南

本文档面向 P0a-lite-2 的作者编辑闭环。作者可以下载生成的
screenplay YAML，修改后通过 `POST /screenplays/validate-yaml` 重新校验。

## 推荐编辑

这些字段主要影响文字表达和改编说明，通常不会破坏引用关系：

- `screenplay.scenes[].title`
- `screenplay.scenes[].summary`
- `screenplay.scenes[].dramatic_goal`
- `screenplay.scenes[].conflict`
- `screenplay.scenes[].content_blocks[].text`
- `screenplay.scenes[].content_blocks[].line`
- `screenplay.scenes[].content_blocks[].emotion`
- `screenplay.scenes[].content_blocks[].action_hint`
- `screenplay.scenes[].adaptation_notes`
- `adaptation_changes[].description`
- `adaptation_changes[].reason`
- `revision_notes[].text`

## 谨慎编辑

这些字段参与排序、定位或引用。可以改，但必须同步维护相关引用：

- `chapters[].chapter_id`
- `screenplay.scenes[].scene_id`
- `screenplay.scenes[].order`
- `screenplay.scenes[].source_chapters`
- `screenplay.scenes[].characters`
- `screenplay.scenes[].location_id`
- `screenplay.scenes[].content_blocks[].block_id`
- `screenplay.scenes[].content_blocks[].order`
- dialogue block 的 `speaker`
- `adaptation_changes[].source_chapters`
- `adaptation_changes[].affected_scenes`

## 不建议手动编辑

这些字段由系统生成或用于校验，不应为了让 YAML “看起来通过”而伪造：

- `metadata.schema_version`
- `metadata.schema_doc_version`
- `metadata.generator_version`
- `metadata.prompt_version`
- `metadata.generated_at`
- `validation`

## `adaptation_changes` 语义

`adaptation_changes` 用来解释对源小说做出的实质改编：

- `merged`: 合并多个源事件或章节段落。
- `omitted`: 删除或跳过源材料。
- `added`: 添加无直接来源的桥段、过场或主剧情材料。
- `reordered`: 调整源材料出现顺序。
- `compressed`: 压缩源材料。
- `expanded`: 扩展源材料。
- `changed_pov`: 改变叙事视角。

非 `added` 的变化必须填写 `source_chapters`。填写
`affected_scenes` 时，值必须指向已有 `scene_id`。如果某章被标记为
`omitted`，该章的 `key_events[].status` 也应标记为 `omitted` 或 `merged`。

## 重新校验

编辑后提交 YAML：

```http
POST /screenplays/validate-yaml
```

请求体：

```json
{
  "yaml": "metadata:\n  ..."
}
```

返回的 `ValidationReport` 中，`errors` 必须为空，且
`yaml_parse_passed`、`schema_validation_passed`、`reference_validation_passed`
和 `coverage_validation_passed` 都应为 `true`，才能认为编辑后的 YAML 可继续使用。
