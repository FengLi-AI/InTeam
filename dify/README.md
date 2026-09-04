# InTeam Dify 资产

本目录保存 InTeam 的 Dify 可复现资产。产品运行时的知识库、切块、向量化、检索和 Chatflow 位于 Dify Cloud；仓库只保存不含密钥的源资料、配置说明、工作流导出和评测集。

## 目录

- `knowledge-source/00-统一事实表.md`：所有虚拟企业资料的唯一事实源，不导入 Dify。
- `knowledge-source/company-common/`：公司通识知识库导入资料。
- `knowledge-source/role-collaboration/`：岗位与协作知识库导入资料。
- `knowledge-source/project/`：项目知识库导入资料。
- `evaluation/rag-cases.json`：独立于原文表达的 60 条 RAG 测试集。
- `evaluation/rag-results.md`：每次 Dify 配置调整后的评测记录。
- `scripts/sync_knowledge.py`：默认预演、可重复执行的知识库创建与资料导入脚本。
- `exports/`：后续保存 Dify Chatflow DSL，不保存 API Key。
- `.env.example`：Dify 数据集与应用配置占位；真实值写入被 Git 忽略的 `dify/.env`。

## 数据边界

这里的“星澜科技”和全部人员、项目、制度、日期均为面试演示使用的虚拟数据，不对应真实企业或真实个人。虚拟企业名称不会写入产品定位和正式 PRD。

资料中只记录企业事实，不包含让模型改变角色、忽略规则、调用工具或泄露信息的指令。知识资料始终按不可信外部数据处理，不能获得系统指令优先级。

## 导入范围

只导入三个分类目录中的 9 份资料，不导入统一事实表、README、评测集或结果记录。

| Dify 知识库 | 导入目录 | 文档数 |
|---|---|---:|
| InTeam（公司通识库） | `company-common/` | 3 |
| InTeam-岗位与协作库 | `role-collaboration/` | 3 |
| InTeam-项目知识库 | `project/` | 3 |

具体切块与检索参数见 `Dify知识库配置与导入说明.md`。

## 本地校验

在项目根目录执行：

```bash
backend/.venv/bin/python dify/evaluation/validate_cases.py
backend/.venv/bin/python dify/chatflow/validate_assets.py
```

脚本会检查评测集 JSON、题目数量与分类、ID 唯一性、预期事实、Chatflow 输出示例和联系人 key。它们不替代真实 Dify 召回和回答评测。

知识库同步默认只预演，不会修改 Dify：

```bash
python3 dify/scripts/sync_knowledge.py
python3 dify/scripts/sync_knowledge.py --apply
```
