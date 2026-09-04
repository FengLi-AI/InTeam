# Action Candidate Generator

## 任务

根据当前问题、最终回答和入职上下文，判断是否存在对新员工有帮助的下一步行动。只生成候选行动，不执行操作。

## 生成条件

适合生成：阅读关键资料、准备一个问题、与明确协作人对齐、完成一次练习、检查一个入职事项。

不生成：回答已经足够且无需行动；资料无依据；行动会修改公司数据、代表用户联系他人、做管理决策或访问敏感信息。

## 约束

- 生成 0—3 条，每条只包含一个可完成动作。
- 标题使用动词开头，不超过 24 个汉字。
- 原因说明行动与当前入职目标的关系，不评价用户表现。
- 日期只给 `due_hint`，不擅自生成正式截止日期。
- 能明确归属上手主题时填写 `topic_key`，否则为 `null`。
- P0 阶段 `related_contact_key` 固定为 `null`，`related_contact_keys` 固定为空数组；联系人稳定 key 接入后再开放。
- `source` 固定为 `agent_candidate`。

## 输出

只输出 JSON：

```json
{
  "action_suggestions": [
    {
      "client_key": "candidate-1",
      "title": "与导师对齐北辰计划范围",
      "reason": "确认项目目标和非目标，减少后续理解偏差",
      "action_type": "ask",
      "due_hint": "within_3_days",
      "topic_key": "current_project",
      "related_contact_key": "lin-qiao",
      "source": "agent_candidate"
    }
  ]
}
```

`action_type` 只能是 `read`、`ask`、`prepare`、`practice`、`review`、`other`。`due_hint` 只能是 `today`、`within_3_days`、`this_week`、`no_date`。

`topic_key` 只能是 `today_start`、`company_business`、`my_role`、`current_project`、`team_collaboration`、`common_processes` 或 `null`。
