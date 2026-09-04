"use client";

import { CalendarDays, Check, ChevronLeft, ChevronRight, Expand, Minimize2, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { addDays, todayString } from "@/lib/date";
import type { TodoItem } from "@/lib/api/types";

type SchedulePanelProps = {
  todos: TodoItem[];
  expanded: boolean;
  busy: boolean;
  onExpandedChange: (expanded: boolean) => void;
  onAdd: (title: string) => void;
  onToggle: (todo: TodoItem) => void;
  onRemove: (id: number) => void;
  onMove: (id: number, dueDate: string) => void;
};

export function SchedulePanel({ todos, expanded, busy, onExpandedChange, onAdd, onToggle, onRemove, onMove }: SchedulePanelProps) {
  const [title, setTitle] = useState("");
  const [offset, setOffset] = useState(0);
  const today = todayString();
  const firstDay = addDays(today, offset * 7);
  const days = useMemo(() => Array.from({ length: 7 }, (_, index) => addDays(firstDay, index)), [firstDay]);
  const overdue = todos.filter((todo) => todo.status === "open" && todo.due_date && todo.due_date < today);

  function submit() {
    const value = title.trim();
    if (!value || busy) return;
    onAdd(value);
    setTitle("");
  }

  function renderTodo(todo: TodoItem) {
    return (
      <div
        className={`todo-chip priority-${todo.priority} ${todo.status === "done" ? "is-done" : ""}`}
        draggable={todo.status !== "done"}
        key={todo.id}
        onDragStart={(event) => event.dataTransfer.setData("todoId", String(todo.id))}
      >
        <button className="todo-check" type="button" onClick={() => onToggle(todo)} aria-label={todo.status === "done" ? "恢复待办" : "完成待办"}>
          {todo.status === "done" && <Check size={11} strokeWidth={3} />}
        </button>
        <span>{todo.title}</span>
        <button className="todo-delete" type="button" onClick={() => onRemove(todo.id)} aria-label={`删除 ${todo.title}`}><Trash2 size={13} /></button>
      </div>
    );
  }

  return (
    <aside className={`panel schedule-panel ${expanded ? "is-expanded" : ""}`} aria-label="待办排期">
      <div className="panel-heading schedule-heading">
        <div className="panel-title-wrap">
          <span className="panel-title-icon"><CalendarDays size={17} /></span>
          <div>
            <p className="eyebrow">THIS WEEK</p>
            <h2>待办排期</h2>
          </div>
        </div>
        <button className="icon-button desktop-only" type="button" onClick={() => onExpandedChange(!expanded)} aria-label={expanded ? "收起排期" : "展开排期"}>
          {expanded ? <Minimize2 size={17} /> : <Expand size={17} />}
        </button>
      </div>

      <div className="schedule-toolbar">
        <button className="icon-button" type="button" onClick={() => setOffset((value) => value - 1)} aria-label="上一周"><ChevronLeft size={16} /></button>
        <button className="week-title" type="button" onClick={() => setOffset(0)}>{offset === 0 ? "本周" : `${firstDay.slice(5).replace("-", ".")} 起`}</button>
        <button className="icon-button" type="button" onClick={() => setOffset((value) => value + 1)} aria-label="下一周"><ChevronRight size={16} /></button>
      </div>

      <div className="todo-create">
        <input value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => event.key === "Enter" && submit()} placeholder="添加待办" aria-label="待办标题" />
        <button type="button" onClick={submit} disabled={!title.trim() || busy} aria-label="添加待办"><Plus size={17} /></button>
      </div>

      <div className="schedule-scroll scroll-area">
        {overdue.length > 0 && (
          <section className="overdue-section">
            <p className="schedule-section-label">需要处理 · {overdue.length}</p>
            <div className="overdue-items">{overdue.map(renderTodo)}</div>
          </section>
        )}

        <div className="week-board">
          {days.map((day, index) => {
            const dayTodos = todos.filter((todo) => todo.due_date === day);
            const date = new Date(`${day}T00:00:00`);
            return (
              <section
                className={`day-column ${day === today ? "is-today" : ""}`}
                key={day}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const id = Number(event.dataTransfer.getData("todoId"));
                  if (id) onMove(id, day);
                }}
              >
                <header className="day-heading">
                  <span>{["日", "一", "二", "三", "四", "五", "六"][date.getDay()]}</span>
                  <strong>{date.getDate()}</strong>
                  {index === 0 && offset === 0 && <small>Today</small>}
                </header>
                <div className="day-dropzone">
                  {dayTodos.length ? dayTodos.map(renderTodo) : <p className="drop-hint">拖到这里</p>}
                </div>
              </section>
            );
          })}
        </div>
        <p className="schedule-footnote">当前待办只有日期粒度，因此按周/日排布，不虚构具体小时。</p>
      </div>
    </aside>
  );
}
