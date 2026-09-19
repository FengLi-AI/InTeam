import type { AgentRun, InformationGap } from "./api";

const LABELS: Record<string, string> = { running: "正在准备", completed: "准备材料已生成", needs_input: "需要补充任务信息", limited: "已整理现有资料", cancelled: "已停止", failed: "未完成", limit: "已达执行上限", interrupted: "运行已中断" };
export const GAP_LABELS = { task_input: "补充任务信息", source_gap: "资料中尚未查到", live_check: "需要现场或负责人确认" };

// Only classify clear task parameters in old records; unknown gaps stay unclassified.
export function informationGaps(run: AgentRun): InformationGap[] {
  if (run.result.information_gaps?.length) return run.result.information_gaps;
  return (run.result.missing_information ?? []).map((text) => ({
    text,
    kind: /本次.{0,8}(议题|需求条目)|评审会议时间|评审时间|参会名单|此次评审中的角色|你在.{0,8}(角色|主讲|旁听)|评审材料.{0,8}(链接|文档)/.test(text) ? "task_input" : "unclassified",
  }));
}

export function runPresentation(run: AgentRun) {
  const gaps = informationGaps(run);
  const taskOnly = gaps.length > 0 && gaps.every((gap) => gap.kind === "task_input");
  const materialReady = run.status === "completed" || (run.status === "limited" && taskOnly && !!run.result.answer && !!run.result.sources?.length);
  const label = materialReady ? "准备材料已生成" : LABELS[run.status] ?? run.status;
  const supplement = !gaps.length ? "" : taskOnly ? `${gaps.length} 项任务信息待补充` : `${gaps.length} 项待补充或核实`;
  return { label, supplement, materialReady, gaps };
}
