import React from "react";
import type { PendingOrder } from "../../types";

interface PendingOrdersSectionProps {
  orders: PendingOrder[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export const PendingOrdersSection: React.FC<PendingOrdersSectionProps> = ({
  orders,
  collapsed = false,
  onToggle,
}) => {
  return (
    <div className="card">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          <svg className="h-4 w-4 text-clinical-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 0 0 2.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 0 0-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75 2.25 2.25 0 0 0-.1-.664m-5.8 0A2.251 2.251 0 0 1 13.5 2.25H15a2.25 2.25 0 0 1 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25Z" />
          </svg>
          Pending Orders
          {orders.length > 0 && (
            <span className="ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-warning-100 px-1.5 text-[10px] font-bold text-warning-600">
              {orders.length}
            </span>
          )}
        </h3>
        <svg
          className={`h-4 w-4 text-slate-400 transition-transform ${collapsed ? "" : "rotate-180"}`}
          fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {!collapsed && (
        <div className="mt-3 space-y-2">
          {orders.length === 0 ? (
            <p className="text-xs text-slate-400">No orders detected yet.</p>
          ) : (
            orders.map((order, idx) => (
              <div
                key={`${order.name}-${order.cpt_code}-${idx}`}
                className="rounded-lg border border-slate-200 bg-white p-2.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-900">
                    {order.name}
                  </span>
                  {order.cpt_code && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                      CPT {order.cpt_code}
                    </span>
                  )}
                </div>
                {order.indication && (
                  <p className="mt-1 text-slate-500">{order.indication}</p>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default PendingOrdersSection;
