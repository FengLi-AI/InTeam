import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentPanel } from "@/features/agent/agent-panel";
import { getAgentConfig, getAgentRuns, streamPreparation, stopAgentRun, getAgentRun } from "@/features/agent/api";

vi.mock("@/features/agent/api", () => ({getAgentConfig:vi.fn(),getAgentRuns:vi.fn(),getAgentRun:vi.fn(),streamPreparation:vi.fn(),stopAgentRun:vi.fn()}));
function mount() {return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><AgentPanel /></QueryClientProvider>);}
beforeEach(()=>{vi.resetAllMocks();vi.mocked(getAgentConfig).mockResolvedValue({enabled:true,ready:true,message:""});vi.mocked(getAgentRuns).mockResolvedValue({items:[]});});
describe("task preparation",()=>{
 it("shows configuration failure instead of pretending to run",async()=>{
  vi.mocked(getAgentConfig).mockResolvedValue({enabled:true,ready:false,message:"任务准备尚未配置模型"});mount();
  expect(await screen.findByRole("alert")).toHaveTextContent("尚未配置模型");
  fireEvent.change(screen.getByLabelText("这次想准备什么？"),{target:{value:"准备讲解"}});
  expect(screen.getByRole("button",{name:"开始准备"})).toBeDisabled();
 });
 it("renders actual tool events and a result, then continues from its run",async()=>{
  vi.mocked(streamPreparation).mockImplementation(async(q,s,p,signal,emit)=>{
   emit({type:"started",run_id:"abc"});emit({type:"trace",event:{seq:1,kind:"tool_start",label:"搜索资料",elapsed_ms:100,tool:"search_knowledge",arguments:{query:"能源主线"}}});
   emit({type:"done",run_id:"abc",status:"completed",result:{title:"讲解准备包",answer:"先说明能源转化。",sources:[{document_id:"hall",title:"展厅主线",excerpt:"能源转化"}],tool_calls:1}});
  });mount();
  await waitFor(()=>expect(screen.getByRole("button",{name:/准备 10 分钟中学生讲解/})).toBeEnabled());
  fireEvent.click(screen.getByRole("button",{name:/准备 10 分钟中学生讲解/}));
  expect(await screen.findByText("讲解准备包")).toBeInTheDocument();
  expect(screen.getByText("能源主线")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("补充要求，继续这次准备"),{target:{value:"改成5分钟"}});
  fireEvent.click(screen.getByRole("button",{name:"开始准备"}));
  await waitFor(()=>expect(vi.mocked(streamPreparation).mock.calls[1][2]).toBe("abc"));
 });
 it("stops the actual run and does not claim completion",async()=>{
  let finish=()=>{};
  vi.mocked(streamPreparation).mockImplementation(async(q,s,p,signal,emit)=>{
   emit({type:"started",run_id:"stop-id"});
   await new Promise<void>((resolve)=>{finish=()=>{emit({type:"done",run_id:"stop-id",status:"cancelled",result:{message:"任务已停止"}});resolve();};});
  });
  vi.mocked(stopAgentRun).mockImplementation(async()=>{finish();return {status:"stopping"};});mount();
  await waitFor(()=>expect(screen.getByRole("button",{name:/准备 10 分钟中学生讲解/})).toBeEnabled());
  fireEvent.click(screen.getByRole("button",{name:/准备 10 分钟中学生讲解/}));
  fireEvent.click(await screen.findByRole("button",{name:"停止准备"}));
  expect(await screen.findByText("任务已停止")).toBeInTheDocument();
  expect(stopAgentRun).toHaveBeenCalledWith("stop-id");
  expect(screen.queryByText("准备材料已生成")).not.toBeInTheDocument();
 });
 it("reopens persisted task history",async()=>{
  vi.mocked(getAgentRuns).mockResolvedValue({items:[{id:"history-id",question:"旧任务",scenario:"exhibition",status:"limited",events:[],result:{title:"历史准备",answer:"设备型号需要核实。"}}]});mount();
  fireEvent.click(await screen.findByText("最近记录"));
  fireEvent.click(await screen.findByRole("button",{name:/旧任务/}));
  expect(screen.getByText("历史准备")).toBeInTheDocument();expect(screen.getByRole("status")).toHaveTextContent("已整理现有资料");
 });
 it.each(["completed", "failed"])("recovers a persisted %s result after a stream interruption",async(status)=>{
  vi.mocked(streamPreparation).mockImplementation(async(q,s,p,signal,emit)=>{
   emit({type:"started",run_id:"recover"});throw new Error("连接中断");
  });
  vi.mocked(getAgentRun).mockResolvedValue({id:"recover",question:"准备讲解",scenario:"exhibition",status,events:[],result:status==="completed"?{title:"已保存成果",answer:"已整理主线"}:{message:"模型暂不可用"}});
  mount();await waitFor(()=>expect(screen.getByRole("button",{name:/准备 10 分钟中学生讲解/})).toBeEnabled());
  fireEvent.click(screen.getByRole("button",{name:/准备 10 分钟中学生讲解/}));
  await screen.findByText(status==="completed"?"已保存成果":"模型暂不可用");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  const input=screen.getByRole("textbox") as HTMLTextAreaElement;
  if(status==="completed") expect(input.value).toBe("");else expect(input.value).toContain("10 分钟");
 });

});
