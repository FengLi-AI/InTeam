import { describe, expect, it } from "vitest";
import { runPresentation } from "@/features/agent/presentation";
import type { AgentRun } from "@/features/agent/api";
const base: AgentRun = {id:"old",question:"准备评审",scenario:"company",status:"limited",events:[],result:{answer:"已整理评审材料",sources:[{document_id:"review",title:"评审规范",excerpt:"材料要求"}]}};
describe("preparation status",()=>{
 it("recognizes the four task details in existing review records",()=>{
  const result=runPresentation({...base,result:{...base.result,missing_information:["本次评审的具体议题/需求条目","评审会议时间与时长（用于倒排材料发布时间）","你在此次评审中的角色（旁听、材料准备人还是需求提出人）","已发布的评审材料链接或文档（若已有）"]}});
  expect(result.label).toBe("准备材料已生成");expect(result.supplement).toBe("4 项任务信息待补充");
 });
 it("does not turn a missing fact into completed work",()=>{
  expect(runPresentation({...base,result:{...base.result,missing_information:["展厅年度发电量"]}}).materialReady).toBe(false);
  expect(runPresentation({...base,result:{...base.result,information_gaps:[{kind:"source_gap",text:"展厅年度发电量"}]}}).label).toBe("已整理现有资料");
 });
 it("keeps clarification and failure distinct even with task gaps",()=>{
  for(const status of ["needs_input","failed","cancelled","limit"]){
   expect(runPresentation({...base,status,result:{...base.result,information_gaps:[{kind:"task_input",text:"讲解时长"}]}}).materialReady).toBe(false);
  }
 });
});
