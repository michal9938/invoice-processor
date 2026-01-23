"use client";

import { useEffect, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import {
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  TrendingUp,
  DollarSign,
  CircleCheck,
  CircleCheckBig,
  CircleCheckBigIcon,
} from "lucide-react";

interface InvoiceStats {
  total: number;
  received: number;
  parsed: number;
  validated: number;
  needs_review: number;
  approved: number;
  total_amount: number;
}

export default function OverviewPage() {
  const [stats, setStats] = useState<InvoiceStats>({
    total: 0,
    received: 0,
    parsed: 0,
    validated: 0,
    needs_review: 0,
    approved: 0,
    total_amount: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const supabase = createSupabaseBrowserClient();

        // Fetch all invoices
        const { data: invoices, error } = await supabase
          .from("invoices")
          .select("status, total_amount");

        if (error) throw error;

        const statsData: InvoiceStats = {
          total: invoices?.length || 0,
          received: 0,
          parsed: 0,
          validated: 0,
          needs_review: 0,
          approved: 0,
          total_amount: 0,
        };

        invoices?.forEach((invoice) => {
          statsData[invoice.status as keyof InvoiceStats]++;
          if (invoice.total_amount) {
            statsData.total_amount += parseFloat(invoice.total_amount.toString());
          }
        });

        setStats(statsData);
      } catch (err: any) {
        console.error("Error fetching stats:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchStats();
  }, []);

  const statCards = [
    {
      title: "Total Invoices",
      value: stats.total,
      icon: FileText,
      color: "from-[#06b6d4] to-[#0891b2]",
      bgColor: "bg-[#06b6d4]/10",
      iconColor: "#06b6d4",

    },
    {
      title: "Needs Review",
      value: stats.needs_review,
      icon: AlertCircle,
      color: "from-[#f59e0b] to-[#ef4444]",
      bgColor: "bg-[#f59e0b]/10",
      iconColor: "#f59e0b",

    },
    
    {
      title: "In Progress",
      value: stats.received + stats.parsed,
      icon: Clock,
      color: "from-[#3b82f6] to-[#2563eb]",
      bgColor: "bg-[#3b82f6]/10",
      iconColor: "#3b82f6",
    },
    {
      title: "Validated",
      value: stats.validated,
      icon: CheckCircle2,
      color: "from-[#10b981] to-[#059669]",
      bgColor: "bg-[#10b981]/10",
      iconColor: "#10b981",
    },
    {
      title: "Approved",
      value: stats.approved,
      icon: CircleCheckBigIcon,
      color: "from-[#059669] to-[#047857]",
      bgColor: "bg-[#059669]/10",
      iconColor: "#059669",
    },
    // {
    //   title: "Total Amount",
    //   value: `$${stats.total_amount.toLocaleString("en-US", {
    //     minimumFractionDigits: 2,
    //     maximumFractionDigits: 2,
    //   })}`,
    //   icon: DollarSign,
    //   color: "from-[#8b5cf6] to-[#7c3aed]",
    //   bgColor: "bg-[#8b5cf6]/10",
    //   iconColor: "#8b5cf6",
    // },
  ];

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8 animate-fade-in">
          <h1 className="text-4xl font-bold gradient-text mb-2">Overview</h1>
       
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="h-32 shimmer rounded-xl border border-border"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            {statCards.map((card, index) => (
              <div
                key={card.title}
                className="relative overflow-hidden flex flex-row items-center justify-between bg-surface rounded-xl p-4 md:p-6 border border-border hover-lift animate-fade-in"
                style={{ animationDelay: `${index * 0.1}s` }}
              >
                <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${card.color} opacity-20 blur-xl absolute -right-4 -top-4`} />
                <div className="flex flex-row items-center gap-3 mb-4 relative z-10">
                  <div
                    className={`w-12 h-12 rounded-lg ${card.bgColor} flex items-center justify-center`}
                  >
                    <card.icon className="w-6 h-6" style={{ color: card.iconColor }} />
                  </div>
                </div>
                <h3 className="text-text-tertiary text-sm font-medium mb-1 relative z-10">
                  {card.title}
                </h3>
                <p className="text-3xl font-bold text-text-primary relative z-10">
                  {card.value}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Status Breakdown - Milestone Style */}
        <div className="bg-surface rounded-xl p-6 border border-border hover-lift animate-fade-in">
          <h2 className="text-2xl font-bold text-text-primary mb-6">
            Invoice Processing Pipeline
          </h2>
          <div className="relative overflow-x-auto pb-4">
            <div className="flex items-center justify-between min-w-max gap-2 md:gap-4 px-4 md:px-8">
              {/* Received */}
              <div className="flex items-center">
                <div className="flex flex-col items-center relative z-10">
                  {/* Milestone Circle */}
                  <div
                    className="w-16 h-16 md:w-20 md:h-20 rounded-full mx-auto mb-2 flex items-center justify-center text-white font-bold text-base md:text-lg shadow-lg border-4 border-surface relative"
                    style={{ backgroundColor: "#3b82f6" }}
                  >
                    {stats.received}
                  </div>
                  {/* Label */}
                  <p className="text-xs md:text-sm text-text-secondary font-medium text-center max-w-[80px] md:max-w-[100px]">
                    Received
                  </p>
                </div>
                {/* Connector Line/Arrow */}
                <div className="flex-1 mx-2 md:mx-4 relative min-w-[40px] md:min-w-[60px]">
                  {/* Thick highlighted line */}
                  <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-gradient-to-r from-[#06b6d4] via-[#0891b2] to-[#06b6d4] transform -translate-y-1/2 rounded-full shadow-sm"></div>
                  {/* Arrow head */}
                  <div className="absolute top-1/2 right-0 transform -translate-y-1/2 translate-x-1/2 z-10">
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-[#06b6d4] drop-shadow-sm"
                    >
                      <path
                        d="M2 10L16 10M16 10L12 6M16 10L12 14"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Parsed */}
              <div className="flex items-center">
                <div className="flex flex-col items-center relative z-10">
                  {/* Milestone Circle */}
                  <div
                    className="w-16 h-16 md:w-20 md:h-20 rounded-full mx-auto mb-2 flex items-center justify-center text-white font-bold text-base md:text-lg shadow-lg border-4 border-surface relative"
                    style={{ backgroundColor: "#8b5cf6" }}
                  >
                    {stats.parsed}
                  </div>
                  {/* Label */}
                  <p className="text-xs md:text-sm text-text-secondary font-medium text-center max-w-[80px] md:max-w-[100px]">
                    Parsed
                  </p>
                </div>
                <div className="flex flex-col gap-12">
                  {/* Connector Line/Arrow */}
                  <div className="flex-1 mx-2 md:mx-4 relative min-w-[40px] md:min-w-[60px] rotate-[325deg]">
                  {/* Thick highlighted line */}
                  <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-gradient-to-r from-[#06b6d4] via-[#0891b2] to-[#06b6d4] transform -translate-y-1/2 rounded-full shadow-sm"></div>
                  {/* Arrow head */}
                  <div className="absolute top-1/2 right-0 transform -translate-y-1/2 translate-x-1/2 z-10">
                    <svg
                      width="20"
                      height="20"
                      viewBox="0 0 20 20"
                      fill="none"
                      className="text-[#06b6d4] drop-shadow-sm"
                    >
                      <path
                        d="M2 10L16 10M16 10L12 6M16 10L12 14"
                        stroke="currentColor"
                        strokeWidth="3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                  </div>
                  {/* Connector Line/Arrow */}
                  <div className="flex-1 mx-2 md:mx-4 relative min-w-[40px] md:min-w-[60px] rotate-[30deg]">
                    {/* Thick highlighted line */}
                    <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-gradient-to-r from-[#06b6d4] via-[#0891b2] to-[#06b6d4] transform -translate-y-1/2 rounded-full shadow-sm"></div>
                    {/* Arrow head */}
                    <div className="absolute top-1/2 right-0 transform -translate-y-1/2 translate-x-1/2 z-10">
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 20 20"
                        fill="none"
                        className="text-[#06b6d4] drop-shadow-sm"
                      >
                        <path
                          d="M2 10L16 10M16 10L12 6M16 10L12 14"
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </div>
                </div>
                
                
              </div>
              <div className="flex flex-col items-center justify-between gap-4">
                {/* Needs Review */}
                <div className="flex items-center">
                  <div className="flex flex-col items-center relative z-10">
                    {/* Milestone Circle */}
                    <div
                      className="w-16 h-16 md:w-20 md:h-20 rounded-full mx-auto mb-2 flex items-center justify-center text-white font-bold text-base md:text-lg shadow-lg border-4 border-surface relative"
                      style={{ backgroundColor: "#f59e0b" }}
                    >
                      {stats.needs_review}
                    </div>
                    {/* Label */}
                    <p className="text-xs md:text-sm text-text-secondary font-medium text-center max-w-[80px] md:max-w-[100px]">
                      Needs Review
                    </p>
                  </div>
                  {/* Connector Line/Arrow */}
                  <div className="flex-1 mx-2 rotate-[30deg] md:mx-4 top-2 relative min-w-[40px] md:min-w-[60px]">
                    {/* Thick highlighted line */}
                    <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-gradient-to-r from-[#06b6d4] via-[#0891b2] to-[#06b6d4] transform -translate-y-1/2 rounded-full shadow-sm"></div>
                    {/* Arrow head */}
                    <div className="absolute top-1/2 right-0 transform -translate-y-1/2 translate-x-1/2 z-10">
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 20 20"
                        fill="none"
                        className="text-[#06b6d4] drop-shadow-sm"
                      >
                        <path
                          d="M2 10L16 10M16 10L12 6M16 10L12 14"
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </div>
                </div>

                {/* Validated */}
                <div className="flex items-center">
                  <div className="flex flex-col items-center relative z-10">
                    {/* Milestone Circle */}
                    <div
                      className="w-16 h-16 md:w-20 md:h-20 rounded-full mx-auto mb-2 flex items-center justify-center text-white font-bold text-base md:text-lg shadow-lg border-4 border-surface relative"
                      style={{ backgroundColor: "#10b981" }}
                    >
                      {stats.validated}
                    </div>
                    {/* Label */}
                    <p className="text-xs md:text-sm text-text-secondary font-medium text-center max-w-[80px] md:max-w-[100px]">
                      Validated
                    </p>
                  </div>
                  {/* Connector Line/Arrow */}
                  <div className="flex-1 mx-2 rotate-[330deg] bottom-7 md:mx-4 relative min-w-[40px] md:min-w-[60px]">
                    {/* Thick highlighted line */}
                    <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-gradient-to-r from-[#06b6d4] via-[#0891b2] to-[#06b6d4] transform -translate-y-1/2 rounded-full shadow-sm"></div>
                    {/* Arrow head */}
                    <div className="absolute top-1/2 right-0 transform -translate-y-1/2 translate-x-1/2 z-10">
                      <svg
                        width="20"
                        height="20"
                        viewBox="0 0 20 20"
                        fill="none"
                        className="text-[#06b6d4] drop-shadow-sm"
                      >
                        <path
                          d="M2 10L16 10M16 10L12 6M16 10L12 14"
                          stroke="currentColor"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
              

              {/* Approved */}
              <div className="flex items-center">
                <div className="flex flex-col items-center relative z-10">
                  {/* Milestone Circle */}
                  <div
                    className="w-16 h-16 md:w-20 md:h-20 rounded-full mx-auto mb-2 flex items-center justify-center text-white font-bold text-base md:text-lg shadow-lg border-4 border-surface relative"
                    style={{ backgroundColor: "#059669" }}
                  >
                    {stats.approved}
                  </div>
                  {/* Label */}
                  <p className="text-xs md:text-sm text-text-secondary font-medium text-center max-w-[80px] md:max-w-[100px]">
                    Approved
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

