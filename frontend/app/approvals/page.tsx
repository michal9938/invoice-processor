"use client";

import { useEffect, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  XCircle,
  ChevronRight,
  DollarSign,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Invoice {
  id: string;
  supplier_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  total_amount: number | null;
  currency: string | null;
  status: string;
  created_at: string;
}

interface ValidationLine {
  id: string;
  status: string;
  expected_unit_price: number | null;
  diff_unit_price: number | null;
  reason: string | null;
  invoice_line: {
    id: string;
    line_no: number;
    sku: string | null;
    product_name: string | null;
    quantity: number | null;
    unit_price: number | null;
    line_total: number | null;
  };
}

export default function ApprovalsPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [validationCounts, setValidationCounts] = useState<
    Record<string, { mismatches: number; noMatches: number }>
  >({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchApprovals() {
      try {
        const supabase = createSupabaseBrowserClient();

        // Fetch only approved/closed invoices
        const { data: invoicesData, error: invoicesError } = await supabase
          .from("invoices")
          .select("*")
          .eq("status", "approved")
          .order("created_at", { ascending: false });

        if (invoicesError) throw invoicesError;

        setInvoices(invoicesData || []);

        // Fetch validation status from invoice lines
        const counts: Record<string, { mismatches: number; noMatches: number }> =
          {};

        for (const invoice of invoicesData || []) {
          const { data: invoiceLines } = await supabase
            .from("invoice_lines")
            .select("status")
            .eq("invoice_id", invoice.id);

          if (invoiceLines && invoiceLines.length > 0) {
            counts[invoice.id] = {
              mismatches:
                invoiceLines.filter((line) => line.status === "mismatch").length || 0,
              noMatches:
                invoiceLines.filter((line) => line.status === "no_match").length || 0,
            };
          } else {
            counts[invoice.id] = { mismatches: 0, noMatches: 0 };
          }
        }

        setValidationCounts(counts);
      } catch (err: any) {
        console.error("Error fetching approvals:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchApprovals();
  }, []);


  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatCurrency = (amount: number | null, currency: string | null) => {
    if (!amount) return "N/A";
    const currencySymbol = currency || "USD";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencySymbol,
    }).format(amount);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8 animate-fade-in">
          <h1 className="text-4xl font-bold gradient-text mb-2">Approvals</h1>
          <p className="text-text-secondary">
            View all approved and closed invoices
          </p>
        </div>

        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="h-32 shimmer rounded-xl border border-border"
              />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <div className="text-center py-12 bg-surface rounded-xl border border-border">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <p className="text-text-secondary text-lg">
              No approved invoices yet
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {invoices.map((invoice, index) => {
              const counts = validationCounts[invoice.id] || {
                mismatches: 0,
                noMatches: 0,
              };
              const hasIssues = counts.mismatches > 0 || counts.noMatches > 0;

              return (
                <div
                  key={invoice.id}
                  className={cn(
                    "bg-surface rounded-xl p-6 border border-border hover-lift animate-fade-in",
                    hasIssues && "border-orange-300 bg-orange-50/50"
                  )}
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-xl font-semibold text-text-primary">
                          {invoice.supplier_name || "Unknown Supplier"}
                        </h3>
                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">
                          Approved
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary mb-4">
                        <span>
                          <strong>Invoice #:</strong>{" "}
                          {invoice.invoice_number || "N/A"}
                        </span>
                        <span>
                          <strong>Date:</strong> {formatDate(invoice.invoice_date)}
                        </span>
                        <span className="flex items-center gap-1">
                          <DollarSign className="w-4 h-4" />
                          <strong>Total:</strong>{" "}
                          {formatCurrency(invoice.total_amount, invoice.currency)}
                        </span>
                      </div>

                      {/* Issue indicators */}
                      {hasIssues && (
                        <div className="flex gap-4 mb-4">
                          {counts.mismatches > 0 && (
                            <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 text-red-700 rounded-lg border border-red-200">
                              <AlertCircle className="w-4 h-4" />
                              <span className="text-sm font-medium">
                                {counts.mismatches} Mismatch
                                {counts.mismatches !== 1 ? "es" : ""}
                              </span>
                            </div>
                          )}
                          {counts.noMatches > 0 && (
                            <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg border border-yellow-200">
                              <XCircle className="w-4 h-4" />
                              <span className="text-sm font-medium">
                                {counts.noMatches} No Match
                                {counts.noMatches !== 1 ? "es" : ""}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <Link
                      href={`/invoices/${invoice.id}`}
                      className="flex-1 px-4 py-2 bg-gradient-to-r from-[#06b6d4] to-[#0891b2] text-white rounded-lg font-medium hover:shadow-lg transition-all duration-200 text-center"
                    >
                      View Details
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

