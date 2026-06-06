import React, { useEffect, useState } from "react";
import api, { currency } from "../lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function AnalyticsPage({ branches, branchId, setBranchId }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    const params = branchId && branchId !== "all" ? { branch_id: branchId } : {};
    api.get("/analytics/summary", { params }).then((r) => setData(r.data));
  }, [branchId]);

  if (!data) return <p>Loading...</p>;

  const stats = [
    { label: "Today", k: "daily", tone: "bg-[#4A5D23]" },
    { label: "This week", k: "weekly", tone: "bg-[#C84B31]" },
    { label: "This month", k: "monthly", tone: "bg-[#8A8D84]" },
    { label: "This year", k: "yearly", tone: "bg-[#1A1C18]" },
  ];

  return (
    <div data-testid="analytics-page">
      <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
        <div>
          <div className="overline text-[#8A8D84]">Analytics</div>
          <h1 className="font-display text-3xl font-semibold">Sales & bookings</h1>
        </div>
        <Select value={branchId} onValueChange={setBranchId}>
          <SelectTrigger data-testid="analytics-branch" className="h-10 rounded-xl w-64"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All branches (aggregated)</SelectItem>
            {branches.map((b) => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map((s) => (
          <div key={s.k} className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-5" data-testid={`stat-${s.k}`}>
            <div className={`h-1.5 w-10 rounded-full ${s.tone} mb-3`} />
            <div className="overline text-[#8A8D84]">{s.label}</div>
            <div className="font-display text-2xl font-semibold mt-1">{currency(data[s.k].sales)}</div>
            <div className="text-xs text-[#5C6056] mt-1">{data[s.k].bookings} bookings</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-5" data-testid="chart-daily">
          <div className="overline text-[#8A8D84] mb-1">Daily sales · last 30 days</div>
          <h3 className="font-display text-lg font-semibold mb-3">Revenue trend</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={data.daily_series}>
                <CartesianGrid stroke="#E5E0D8" strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#8A8D84" }} />
                <YAxis tick={{ fontSize: 10, fill: "#8A8D84" }} />
                <Tooltip formatter={(v) => currency(v)} contentStyle={{ borderRadius: 12, border: "1px solid #E5E0D8" }} />
                <Line type="monotone" dataKey="sales" stroke="#4A5D23" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-[#E5E0D8] shadow-soft p-5" data-testid="chart-monthly">
          <div className="overline text-[#8A8D84] mb-1">Monthly bookings</div>
          <h3 className="font-display text-lg font-semibold mb-3">Booking volume</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={data.monthly_series}>
                <CartesianGrid stroke="#E5E0D8" strokeDasharray="3 3" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#8A8D84" }} />
                <YAxis tick={{ fontSize: 10, fill: "#8A8D84" }} />
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E5E0D8" }} />
                <Bar dataKey="bookings" fill="#C84B31" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
