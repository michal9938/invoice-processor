"use client";

import { useEffect, useState, useCallback } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import {
  CheckCircle2,
  AlertCircle,
  XCircle,
  Package,
  DollarSign,
  Calendar,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface BuyingPriceRecord {
  id: string;
  supplier_name: string;
  sku: string | null;
  product_name: string | null;
  currency: string;
  unit_price: number;
  status: "active" | "need_review" | "inactive";
  valid_from: string | null;
  valid_to: string | null;
  source: string;
  note: string | null;
  created_at: string;
  created_by: string | null;
}

export default function PriceRecordsPage() {
  const [records, setRecords] = useState<BuyingPriceRecord[]>([]);
  const [allRecords, setAllRecords] = useState<BuyingPriceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    async function fetchPriceRecords() {
      try {
        const supabase = createSupabaseBrowserClient();

        const { data, error } = await supabase
          .from("buying_price_records")
          .select("*")
          .order("created_at", { ascending: false });

        if (error) throw error;
        const fetchedRecords = data || [];
        setAllRecords(fetchedRecords);
        setRecords(fetchedRecords);
      } catch (err: any) {
        console.error("Error fetching price records:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchPriceRecords();
  }, []);

  // Search function to filter records
  const performSearch = useCallback(() => {
    if (!searchTerm.trim()) {
      setRecords(allRecords);
      return;
    }

    const searchLower = searchTerm.toLowerCase();
    const filtered = allRecords.filter((record) => {
      const matchesSKU = record.sku?.toLowerCase().includes(searchLower);
      const matchesSupplier = record.supplier_name
        ?.toLowerCase()
        .includes(searchLower);
      const matchesProduct = record.product_name
        ?.toLowerCase()
        .includes(searchLower);
      return matchesSKU || matchesSupplier || matchesProduct;
    });

    setRecords(filtered);
  }, [searchTerm, allRecords]);

  // Filter records based on search term (real-time)
  useEffect(() => {
    performSearch();
  }, [performSearch]);

  // Handle Enter key press
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      performSearch();
    }
  };

  const handleActivate = async (record: BuyingPriceRecord) => {
    if (!record.sku) {
      alert("Cannot activate: SKU is missing");
      return;
    }

    setActivatingId(record.id);

    try {
      const supabase = createSupabaseBrowserClient();

      // First, find and deactivate previous active records with the same SKU
      const { data: previousActive, error: findError } = await supabase
        .from("buying_price_records")
        .select("id")
        .eq("supplier_name", record.supplier_name)
        .eq("sku", record.sku)
        .eq("status", "active")
        .neq("id", record.id);

      if (findError) throw findError;

      // Deactivate previous active records
      if (previousActive && previousActive.length > 0) {
        const previousIds = previousActive.map((r) => r.id);
        const { error: deactivateError } = await supabase
          .from("buying_price_records")
          .update({ status: "inactive" })
          .in("id", previousIds);

        if (deactivateError) throw deactivateError;
      }

      // Activate the current record
      const { error: activateError } = await supabase
        .from("buying_price_records")
        .update({ status: "active" })
        .eq("id", record.id);

      if (activateError) throw activateError;

      // Update invoice_lines status to 'match' for lines with same SKU and status 'created_price_record'
      // This ensures that when a price record is approved, all related invoice lines are marked as matched
      if (record.sku) {
        // First, get the invoice_id for the invoice_lines we need to update
        const { data: invoiceLines, error: linesError } = await supabase
          .from("invoice_lines")
          .select("id, invoice_id")
          .eq("sku", record.sku)
          .eq("status", "created_price_record");

        if (linesError) throw linesError;

        // Get supplier_name from invoices to match
        if (invoiceLines && invoiceLines.length > 0) {
          const invoiceIds = [...new Set(invoiceLines.map((line) => line.invoice_id))];
          
          // Check if invoices match the supplier
          const { data: invoices, error: invoicesError } = await supabase
            .from("invoices")
            .select("id")
            .in("id", invoiceIds)
            .eq("supplier_name", record.supplier_name);

          if (invoicesError) throw invoicesError;

          if (invoices && invoices.length > 0) {
            const matchingInvoiceIds = invoices.map((inv) => inv.id);
            const matchingLineIds = invoiceLines
              .filter((line) => matchingInvoiceIds.includes(line.invoice_id))
              .map((line) => line.id);

            if (matchingLineIds.length > 0) {
              // Update invoice_lines status to 'match'
              const { error: updateLinesError } = await supabase
                .from("invoice_lines")
                .update({ status: "match" })
                .in("id", matchingLineIds);

              if (updateLinesError) throw updateLinesError;
            }
          }
        }
      }

      // Update local state for both allRecords and records
      const updateRecord = (r: BuyingPriceRecord): BuyingPriceRecord => {
        if (r.id === record.id) {
          return { ...r, status: "active" as const };
        }
        if (
          previousActive?.some((pa) => pa.id === r.id) &&
          r.status === "active"
        ) {
          return { ...r, status: "inactive" as const };
        }
        return r;
      };

      setAllRecords((prev) => prev.map(updateRecord));
      setRecords((prev) => prev.map(updateRecord));
    } catch (err: any) {
      console.error("Error activating price record:", err);
      alert(`Failed to activate price record: ${err.message}`);
    } finally {
      setActivatingId(null);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
    }).format(amount);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">
            <CheckCircle2 className="w-3 h-3" />
            Active
          </span>
        );
      case "need_review":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700 border border-yellow-200">
            <AlertCircle className="w-3 h-3" />
            Need Review
          </span>
        );
      case "inactive":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
            <XCircle className="w-3 h-3" />
            Inactive
          </span>
        );
      default:
        return null;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="h-96 shimmer rounded-xl border border-border" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8 animate-fade-in">
          <h1 className="text-4xl font-bold gradient-text mb-2">
            Price Records
          </h1>
          <p className="text-text-secondary">
            Manage buying price records for automatic validation
          </p>
        </div>

        {/* Search Bar */}
        <div className="mb-6 animate-fade-in">
          <div className="relative">
            <Search 
              className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-text-tertiary cursor-pointer hover:text-text-secondary transition-colors" 
              onClick={performSearch}
            />
            <input
              type="text"
              placeholder="Search by SKU, Supplier, or Product..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full pl-10 pr-4 py-2 bg-surface border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
          </div>
        </div>

        {/* Price Records Table */}
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="p-6 border-b border-border">
            <h2 className="text-2xl font-bold text-text-primary">
              Buying Price Records
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-surface-elevated">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Supplier
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    SKU
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Product
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Unit Price
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Valid From
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Valid To
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {records.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-6 py-12 text-center">
                      <Package className="w-12 h-12 text-text-muted mx-auto mb-4" />
                      <p className="text-text-secondary">
                        {searchTerm.trim()
                          ? "No price records match your search"
                          : "No price records found"}
                      </p>
                    </td>
                  </tr>
                ) : (
                  records.map((record, index) => {
                    const isNeedReview = record.status === "need_review";
                    const isActivating = activatingId === record.id;

                    return (
                      <tr
                        key={record.id}
                        className={cn(
                          "hover:bg-surface-elevated transition-colors animate-fade-in",
                          isNeedReview && "bg-yellow-50/50"
                        )}
                        style={{ animationDelay: `${index * 0.05}s` }}
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-primary">
                          {record.supplier_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                          {record.sku || "—"}
                        </td>
                        <td className="px-6 py-4 text-sm text-text-primary">
                          <div>
                            <div className="font-medium">
                              {record.product_name || "—"}
                            </div>
                            {record.note && (
                              <div className="text-text-tertiary text-xs mt-1">
                                {record.note}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-text-primary">
                          {formatCurrency(record.unit_price, record.currency)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                          {formatDate(record.valid_from)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                          {formatDate(record.valid_to)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {getStatusBadge(record.status)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          {record.status === "need_review" && (
                            <button
                              onClick={() => handleActivate(record)}
                              disabled={isActivating || !record.sku}
                              className={cn(
                                "px-4 py-1.5 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg text-xs font-medium hover:shadow-lg transition-all duration-200 flex items-center gap-1.5",
                                (isActivating || !record.sku) &&
                                  "opacity-50 cursor-not-allowed"
                              )}
                            >
                              {isActivating ? (
                                <>
                                  <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                  Activating...
                                </>
                              ) : (
                                <>
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  Approve
                                </>
                              )}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

