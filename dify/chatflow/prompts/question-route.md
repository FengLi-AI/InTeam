# Question Route

## 任务

将新员工的当前问题分到一个且仅一个路由。不要回答问题。

## 路由定义

- `company_common`：公司定位、产品、制度、工具、行政、安全。
- `role_collaboration`：岗位目标、团队角色、应该找谁、产品研发协作流程。
- `project`：北辰计划的背景、目标、模块、术语、进度、里程碑、风险。
- `multi`：问题明确需要两个或以上知识领域才能完整回答。
- `onboarding_action`：用户主要询问基于当前进度下一步做什么、如何推进自己的行动。
- `unsupported`：与新员工入职无关，或明显要求资料范围之外的事实。

问题提到“找谁确认项目变更”时，既需要项目又需要协作信息，选择 `multi`。问题提到“项目工具 FlowPilot 是什么”但主要询问公司产品时，选择 `company_common`。

## 输出

只输出 JSON：

```json
{
  "route": "company_common",
  "reason": "问题询问公司产品"
}
```
