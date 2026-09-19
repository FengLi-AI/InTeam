# InTeam Chatflow 蓝图

> 版本：v1.9
> 状态：2026-09-19 检索修复；验证结果见 `../../docs/agent-release-v1.9.md`
> 当前导出：`../exports/InTeam-Onboarding-Agent-v1.9-published.yml`
> 历史回滚文件：`../exports/InTeam-Onboarding-Agent-v1.6-published.yml`

## 1. 应用类型

创建 Dify Chatflow，应用名建议为 `InTeam-Onboarding-Agent`。P0 不给 Agent 配置任何能修改 InTeam 数据的 Tool。工作流只返回回答、追问和候选行动，正式行动由用户在 InTeam 前端确认后通过 FastAPI 创建。

## 2. 输入

| 变量 | 类型 | 必填 | 来源 | 说明 |
|---|---|---|---|---|
| `sys.query` | string | 是 | Dify | 当前用户问题 |
| `onboarding_context` | string | 是 | FastAPI | 最小化 JSON：岗位、入职阶段、地图进度和未完成行动摘要 |
| `current_date` | string | 是 | FastAPI | ISO 日期，避免模型把计划当成当前事实 |
| `locale` | string | 否 | FastAPI | P0 固定 `zh-CN` |

`onboarding_context` 不包含 Cookie、邀请码、API Key、完整数据库记录、其他用户信息或 Dify 内部 ID。

## 3. 当前已发布节点

P0 当前采用已验证的最小 Chatflow，不把规划中的复杂路由一次性全部引入：

```text
用户输入 → 知识检索（三个知识库） → 企业知识回答 → 回复用户 → 结构化建议
```

- `企业知识回答`：Aihubmix 的 `DeepSeek V4 Flash`，负责员工可见正文。
- `结构化建议`：Aihubmix 的 `DeepSeek V4 Flash`，开启 Structured Output，负责追问和候选行动。
- Embedding 使用 AI Hub Mix 的 `qwen3-embedding-4b`；当前使用语义 0.7 / 关键词 0.3 的权重排序，不调用外部 Rerank 模型。召回上限为 20，关闭分数阈值，适用于当前的小规模资料库。
- `回复用户` 先于结构化建议执行，附加建议异常时正文仍可正常完成。

以下节点表是后续按评测结果逐步扩展的目标蓝图，而不是当前线上节点清单。

## 4. 目标节点蓝图

| 编号 | 节点名 | Dify 节点类型 | 主要输出 |
|---|---|---|---|
| N01 | Start | Start | 输入变量 |
| N02 | Security Gate | LLM / Parameter Extractor | `decision`、`risk_type` |
| N03 | Security Branch | IF/ELSE | allow / refuse |
| N04 | Safe Refusal | Template | 克制的拒绝文案 |
| N05 | Question Route | Question Classifier | `route` |
| N06 | Company Retrieval | Knowledge Retrieval | 公司通识片段 |
| N07 | Role Retrieval | Knowledge Retrieval | 岗位协作片段 |
| N08 | Project Retrieval | Knowledge Retrieval | 项目片段 |
| N09 | Multi Retrieval | Knowledge Retrieval | 三库片段 |
| N10 | Context Aggregator | Variable Aggregator | 统一 `retrieval_context` |
| N11 | Evidence Judge | LLM / Parameter Extractor | `answer_status` |
| N12 | Answer | LLM | 纯回答正文 |
| N13 | Stream Answer | Answer | 向用户流式输出 N12 文本 |
| N14 | Follow-up Generator | LLM / Parameter Extractor | 最多 3 个追问 |
| N15 | Action Candidate Generator | LLM / Parameter Extractor | 最多 3 个候选行动 |
| N16 | Contact Key Extractor | LLM / Parameter Extractor | 相关同事 key |
| N17 | End | End | 结构化 outputs |

如果当前 Dify 版本不能让 Answer 节点之后继续执行，则将 N14—N16 放到 N12 前并行执行，或由一个结构化 LLM 节点一次生成；不能为了省节点把 JSON 混入用户可见回答。

## 5. 目标路由

```text
N01 → N02 → N03
N03(refuse) → N04 → N17
N03(allow) → N05
N05(company_common) → N06 → N10
N05(role_collaboration) → N07 → N10
N05(project) → N08 → N10
N05(multi) → N09 → N10
N05(onboarding_action) → N10（只使用 onboarding_context）
N05(unsupported) → N11（无检索上下文）
N10 → N11 → N12 → N13 → N14 → N15 → N16 → N17
```

## 6. 问题分类

| route | 含义 | 检索范围 |
|---|---|---|
| `company_common` | 公司、产品、制度、工具、安全 | 公司通识库 |
| `role_collaboration` | 岗位目标、同事职责、研发协作 | 岗位与协作库 |
| `project` | 北辰计划背景、模块、里程碑、风险 | 项目知识库 |
| `multi` | 一个问题明确跨越两个以上领域 | 三个知识库 |
| `onboarding_action` | 基于已有回答或进度询问下一步 | 不强制检索，使用上手上下文 |
| `unsupported` | 与入职无关或资料范围外 | 不检索，安全降级 |

分类不确定时选择 `multi`，不要只因问题包含“项目”二字就忽略其中的制度或协作问题。

## 7. answer_status

| 状态 | 条件 | 回答要求 |
|---|---|---|
| `reliable` | 召回内容直接、无冲突地支持回答 | 清楚回答，可给行动建议 |
| `limited` | 只有部分问题有依据，或资料明确但不完整 | 只回答有依据部分，说明哪部分待确认 |
| `not_found` | 没有相关企业资料，或问题要求当前资料之后的事实 | 明确知识库未收录，不用常识补全 |
| `blocked` | 请求系统提示词、密钥、源码、越权或未经确认的业务写入 | 拒绝敏感部分，并引导到正常入职问题 |

## 8. 结构化附加输出

当前应用为 Chatflow，`workflow_finished.outputs` 只返回 `answer/files`。不要照搬 Workflow 应用的“输出”节点配置。

在 `回复用户` 之后连接一个固定命名为 `结构化建议` 的 LLM 节点，开启 Structured Output，并返回以下变量：

- `answer_status`
- `suggested_questions`
- `action_suggestions`
- `related_contact_keys`

结构以 `contracts/workflow-outputs.schema.json` 为准。FastAPI 只读取该固定节点的 `node_finished.data.outputs.structured_output`；如果 Dify 返回 JSON 字符串，则先解析再校验。解析失败时返回空数组，不能把原始模型输出透传给前端。

同事标识必须使用 `contracts/contact-keys.json` 中的稳定 key，不直接依赖姓名匹配。现有后端仍是旧版联系人种子，P0-3 必须迁移后才能启用 `related_contact_keys`；未知 key 由 FastAPI 丢弃并记录告警。

## 9. 安全边界

- Knowledge Retrieval 返回内容只作为资料，不作为指令。
- 系统提示词、节点配置、API Key、内部日志和服务端源码不进入回答。
- P0 不接创建、修改、删除行动项的 Tool。
- 候选行动必须标记为 `agent_candidate`，不能使用“已创建”“已联系”等完成态措辞。
- 不模拟同事在线状态，不声称已经向同事发送消息。
- 不向员工端返回检索片段、文件名、相关性分数、模型思维链或节点执行详情。

## 10. 发布与验证记录

- Dify 发布版本：`#6`，发布时间 2026-09-01。
- 真实 Service API：HTTP 200；检测到 `结构化建议` 节点及结构化对象。
- 实际字段：`answer_status`、3 个追问、候选行动、关联主题。
- InTeam 后端闭环：候选建议入库 → 用户接受 → 行动完成 → `current_project` 从 `exploring` 更新为 `completed`。
- DSL 已检查：不含有效密钥；SHA-256 为 `43b38d7c9f3ee19ff4d2b6dadbbb5183d970a8a324e0fc390db338b8096d34d6`。
- 60 条 Case 当前只完成静态契约校验；完整线上逐题评测仍需另行执行，不能把静态校验记作回答通过率。

## 11. 后续必须完成

1. 在 Dify 控制台逐节点测试分类、空召回、部分召回和拒绝路径。
2. 使用 `../evaluation/rag-cases.json` 执行 60 条评测。
3. 验证用户未确认时不会产生任何 InTeam 数据写入。
4. 每次修改后发布 Chatflow，并确认 Service API Key 只保存在后端环境。
5. 每次发布后重新导出 DSL 到 `../exports/`，检查导出文件不包含有效密钥。

Question Classifier 和变量聚合方式可参考 Dify 官方节点说明与工作流分支教程：

- [Question Classifier 节点接口](https://docs.dify.ai/en/develop-plugin/features-and-specs/advanced-development/reverse-invocation-node)
- [分支与 Variable Aggregator 教程](https://docs.dify.ai/ja/use-dify/tutorials/workflow-101/lesson-05)
