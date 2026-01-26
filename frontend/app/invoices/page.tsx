"use client";

import { useEffect, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  FileText,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Clock,
  Archive,
  Search,
  Filter,
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

const vendors = ["Alpine", "Sonova", "Ascon", "MG development","CoolSafety", "Audinell", "Bernafon", "Duraxx", "Ewanto", "GN Hearing", "Oticon", "Phonak", "Sivantos", "Sivantos A/S", "Starkey", "Widex", 'unitron', 'Private Uafhængige']

const statusConfig: Record<string, { label: string; color: string; icon: any }> =
  {
    received: {
      label: "Received",
      color: "bg-blue-100 text-blue-700 border-blue-200",
      icon: Clock,
    },
    parsed: {
      label: "Parsed",
      color: "bg-purple-100 text-purple-700 border-purple-200",
      icon: FileText,
    },
    validated: {
      label: "Validated",
      color: "bg-green-100 text-green-700 border-green-200",
      icon: CheckCircle2,
    },
    needs_review: {
      label: "Needs Review",
      color: "bg-orange-100 text-orange-700 border-orange-200",
      icon: AlertCircle,
    },
    closed: {
      label: "Closed",
      color: "bg-gray-100 text-gray-700 border-gray-200",
      icon: Archive,
    },
  };

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  useEffect(() => {
    async function fetchInvoices() {
      try {
        const supabase = createSupabaseBrowserClient();

        let query = supabase
          .from("invoices")
          .select("*")
          .order("created_at", { ascending: false });

        if (statusFilter !== "all") {
          query = query.eq("status", statusFilter);
        }

        const { data, error } = await query;
        console.log(data);
        if (error) throw error;
        setInvoices(data || []);
      } catch (err: any) {
        console.error("Error fetching invoices:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchInvoices();
  }, [statusFilter]);

  // const filteredInvoices = invoices.filter((invoice) => {
  //   const searchLower = searchTerm.toLowerCase();
  //   return (
  //     invoice.supplier_name?.toLowerCase().includes(searchLower) ||
  //     invoice.invoice_number?.toLowerCase().includes(searchLower) ||
  //     false
  //   );
  // });

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
          <h1 className="text-4xl font-bold gradient-text mb-2">Invoices</h1>
          <p className="text-text-secondary">
            View and manage all invoices in the system
          </p>
        </div>

        {/* Filters */}
        {/* <div className="mb-6 flex flex-col sm:flex-row gap-4 animate-fade-in">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-tertiary" />
            <input
              type="text"
              placeholder="Search by supplier or invoice number..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
          </div>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-tertiary" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="pl-10 pr-8 py-2 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent appearance-none cursor-pointer"
            >
              <option value="all">All Status</option>
              <option value="received">Received</option>
              <option value="parsed">Parsed</option>
              <option value="validated">Validated</option>
              <option value="needs_review">Needs Review</option>
              <option value="closed">Closed</option>
            </select>
          </div>
        </div> */}

        {loading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className="h-24 shimmer rounded-xl border border-border"
              />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <div className="text-center py-12 bg-surface rounded-xl border border-border">
            <FileText className="w-16 h-16 text-text-muted mx-auto mb-4" />
            <p className="text-text-secondary text-lg">
              No invoices found
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {invoices.map((invoice, index) => {
              const statusInfo = statusConfig[invoice.status] || statusConfig.received;
              const StatusIcon = statusInfo.icon;

              return (
                <Link
                  key={invoice.id}
                  href={`/invoices/${invoice.id}`}
                  className="block"
                >
                  <div
                    className={cn(
                      "bg-surface rounded-xl p-6 border border-border hover-lift animate-fade-in cursor-pointer",
                      invoice.status === "needs_review" &&
                        "border-orange-300 bg-orange-50/50"
                    )}
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-lg font-semibold text-text-primary truncate">
                            {vendors.includes(invoice.supplier_name || "") ? invoice.supplier_name : "Unknown Supplier"}
                          </h3>
                          <span
                            className={cn(
                              "px-3 py-1 rounded-full text-xs font-medium border flex items-center gap-1.5 whitespace-nowrap",
                              statusInfo.color
                            )}
                          >
                            <StatusIcon className="w-3.5 h-3.5" />
                            {invoice.status}
                          </span>
                        </div>
                        <div className="flex flex-wrap items-center gap-4 text-sm text-text-secondary">
                          <span>
                            <strong>Invoice #:</strong>{" "}
                            {invoice.invoice_number || "N/A"}
                          </span>
                          <span>
                            <strong>Date:</strong> {formatDate(invoice.invoice_date)}
                          </span>
                          <span>
                            <strong>Amount:</strong>{" "}
                            {formatCurrency(invoice.total_amount, invoice.currency)}
                          </span>
                        </div>
                      </div>
                      <ChevronRight className="w-6 h-6 text-text-tertiary ml-4 flex-shrink-0" />
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

