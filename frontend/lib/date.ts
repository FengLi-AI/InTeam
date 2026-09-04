export function todayString(now = new Date()) {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function addDays(dateString: string, amount: number) {
  const date = new Date(`${dateString}T00:00:00`);
  date.setDate(date.getDate() + amount);
  return todayString(date);
}

export function dayLabel(dateString: string, today = todayString()) {
  if (dateString === today) return "今天";
  if (dateString === addDays(today, 1)) return "明天";
  const date = new Date(`${dateString}T00:00:00`);
  const week = ["日", "一", "二", "三", "四", "五", "六"][date.getDay()];
  return `${date.getMonth() + 1}/${date.getDate()} 周${week}`;
}
