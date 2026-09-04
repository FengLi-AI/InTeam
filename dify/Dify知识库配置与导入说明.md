# InTeam Dify 知识库配置与导入说明

> 版本：v1.0
> 日期：2026-09-01
> 当前状态：Dify Cloud 已配置 3 个知识库和 9 份资料；岗位库、项目库已完成 API 导入和关键问题召回抽查

## 一、前置条件

需要在 Dify Cloud 中准备：

1. 一个只用于 InTeam 的工作区。
2. 可用的中文 Embedding 模型。
3. 可选的 Rerank 模型。
4. 知识库管理 API Key。Key 只填写到本地 `.env`，不进入仓库、前端或截图。

Dify 官方文档要求知识库 API 通过 `Authorization: Bearer {API_KEY}` 鉴权，并建议只在服务端保存 Key。真实 Key 只保存在被 Git 忽略的 `dify/.env`。

## 二、知识库划分

| 知识库名称 | 导入资料 | 索引 | 切块模式 | 用途 |
|---|---|---|---|---|
| InTeam（公司通识库） | `knowledge-source/company-common/*.md` | High Quality | Parent-child | 公司、产品、制度、安全与工具 |
| InTeam-岗位与协作库 | `knowledge-source/role-collaboration/*.md` | High Quality | General | 岗位目标、团队角色、协作流程 |
| InTeam-项目知识库 | `knowledge-source/project/*.md` | High Quality | Parent-child | 北辰计划背景、模块、里程碑和风险 |

三个知识库均设为工作区私有。不要导入 `00-统一事实表.md`，否则会制造重复片段并让评测结果虚高。

## 三、初始切块参数

参数是第一轮评测起点，不是固定最佳值。最终以 60 条测试集结果为准。

### 3.1 公司通识库

- 分段模式：General。
- 分隔符：两个换行，即自然段。
- 单块最大长度：500 tokens。
- overlap：50 tokens。
- 清理连续空格和空行，不移除标题。

### 3.2 岗位与协作库

- 分段模式：General。
- 分隔符：两个换行。
- 单块最大长度：450 tokens。
- overlap：40 tokens。
- 人员职责与“谁确认什么”尽量保留在同一块。

### 3.3 项目知识库

- 分段模式：Parent-child。
- Parent mode：Paragraph。
- 父块最大长度：900 tokens。
- 子块最大长度：220 tokens。
- 子块 overlap：30 tokens。
- 里程碑日期、状态和准入条件不能被拆成互不相邻的三块。

## 四、初始检索参数

在 Chatflow 的 Knowledge Retrieval 节点中设置：

- 检索方式：Hybrid Search。
- Top K：10。首轮实测中 Top K 5 会让“30 天目标”和“Alpha 准入条件”的准确片段在 Rerank 前被截断；当前资料量较小，先扩大候选池保证召回。
- Score threshold：先使用 0.35。
- 语义权重：0.7；关键词权重：0.3。
- Rerank：工作区已有可用模型时开启；没有时先不增加外部依赖。

阈值只在所选 Embedding/Rerank 模型固定后才有可比性。若未收录问题经常产生伪命中，先提高 threshold；若正确资料召回不足，先检查切块和问题路由，再考虑降低 threshold，不直接用更宽松 Prompt 掩盖检索问题。

## 五、控制台导入步骤

1. 在 Dify 创建三个空知识库，名称与第二节一致。
2. 分别选择 High Quality 索引和对应切块模式。
3. 上传分类目录中的 3 份 Markdown；不要上传整个 `dify/` 目录。
4. 预览切块，重点检查标题、人员职责、里程碑日期和否定规则是否完整。
5. 等待全部文档状态变为 Available。
6. 在知识库检索测试中先抽查每类 5 题。
7. 在 Chatflow 知识检索节点连接三个知识库，按问题分类限定检索范围。
8. 完成 60 条全量评测，并把结果写入 `evaluation/rag-results.md`。

## 六、文档元数据

如当前 Dify 版本支持文档元数据，建议记录：

| 字段 | 示例 |
|---|---|
| `kb_type` | `company_common` / `role_collaboration` / `project` |
| `doc_version` | `2026-09-01` |
| `effective_date` | `2026-09-01` |
| `data_nature` | `synthetic_demo` |
| `product` | `InTeam` |

元数据用于检索过滤和维护，不向员工端展示。

## 七、资料更新规则

1. 先修改 `00-统一事实表.md`，为新事实分配 ID。
2. 再修改对应导入资料，检查其他文档是否存在冲突。
3. 在 Dify 更新文档并等待重新索引完成。
4. 执行受影响问题和 10 条未收录问题，再执行 60 条全量回归。
5. 记录知识库版本、模型、切块、检索参数、通过率和失败原因。
6. 只有评测达标后，才让新版本进入 InTeam Chatflow。

不要在 Dify 控制台直接临时改出一份仓库中不存在的资料。仓库源文件是演示资料的版本依据，Dify 是运行时知识载体。

## 八、验收规则

- 50 条知识内问题中，正确资料召回率至少 90%。
- 10 条未收录问题不得生成确定的企业事实。
- 时间敏感问题必须区分已完成、计划和当前阻塞。
- 问题路由不得让公司制度问题只检索项目库。
- 员工端不展示文件名、片段、相关性分数或 Dify 节点信息。
- 知识库资料中的文字不能改变系统角色或触发业务写操作。

## 九、自动化同步

`scripts/sync_knowledge.py` 只从 `knowledge-source/role-collaboration/` 和 `knowledge-source/project/` 读取资料，用于创建和初始化两个知识库。脚本具备以下保护：

- 默认 dry-run，明确指定知识库才上传。
- 先按文档名查询，避免重复创建。
- 已存在的同名文档直接跳过，不静默覆盖。
- 上传后轮询至 Available，并拒绝字数为 0 的空索引结果。
- 日志只输出知识库 ID、文档名和状态，不输出 Authorization Header。

在项目根目录执行预演：

```bash
python3 dify/scripts/sync_knowledge.py
```

确认后执行真实同步：

```bash
python3 dify/scripts/sync_knowledge.py --apply
```

官方接口参考：

- [获取知识库的文档列表](https://docs.dify.ai/api-reference/%E6%96%87%E6%A1%A3/%E8%8E%B7%E5%8F%96%E7%9F%A5%E8%AF%86%E5%BA%93%E7%9A%84%E6%96%87%E6%A1%A3%E5%88%97%E8%A1%A8)
- [获取父块的子块](https://docs.dify.ai/api-reference/%E3%83%81%E3%83%A3%E3%83%B3%E3%82%AF/%E5%AD%90%E3%83%81%E3%83%A3%E3%83%B3%E3%82%AF%E3%82%92%E5%8F%96%E5%BE%97)
