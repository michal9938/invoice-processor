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
  Filter,
  ChevronDown,
  Edit2,
  Save,
  X,
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
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "need_review">("all");
  const [showStatusFilter, setShowStatusFilter] = useState(false);
  const [editingPriceId, setEditingPriceId] = useState<string | null>(null);
  const [editingPriceValue, setEditingPriceValue] = useState<string>("");
  const [updatingPriceId, setUpdatingPriceId] = useState<string | null>(null);

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

  // Filter function to filter records by search term and status
  const performSearch = useCallback(() => {
    let filtered = allRecords;

    // Apply status filter
    if (statusFilter !== "all") {
      filtered = filtered.filter((record) => record.status === statusFilter);
    }

    // Apply search filter
    if (searchTerm.trim()) {
      const searchLower = searchTerm.toLowerCase();
      filtered = filtered.filter((record) => {
        const matchesSKU = record.sku?.toLowerCase().includes(searchLower);
        const matchesSupplier = record.supplier_name
          ?.toLowerCase()
          .includes(searchLower);
        const matchesProduct = record.product_name
          ?.toLowerCase()
          .includes(searchLower);
        return matchesSKU || matchesSupplier || matchesProduct;
      });
    }

    setRecords(filtered);
  }, [searchTerm, statusFilter, allRecords]);

  // Filter records based on search term and status filter (real-time)
  useEffect(() => {
    performSearch();
  }, [performSearch]);

  // Close status filter dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!target.closest('.status-filter-container')) {
        setShowStatusFilter(false);
      }
    };

    if (showStatusFilter) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showStatusFilter]);

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

      // Determine valid_from date: use existing valid_from if set, otherwise use today
      const today = new Date().toISOString().split('T')[0];
      const validFrom = record.valid_from || today;
      // First, find and deactivate ALL previous active records with the same SKU (not just different id)
      const { data: previousActive, error: findError } = await supabase
        .from("buying_price_records")
        .select("id, valid_from")
        .eq("sku", record.sku)
        .eq("product_name", record.product_name)
        .eq("status", "active")
        .neq("id", record.id);
      console.log(" - - - - -", record.supplier_name, record.sku)
      if (findError) throw findError;
      console.log("- - - ", previousActive)
      // Deactivate previous active records and set their valid_to to the day before the new record's valid_from
      if (previousActive && previousActive.length > 0) {
        const previousIds = previousActive.map((r) => r.id);
        
        // Calculate valid_to date (day before valid_from)
        const validFromDate = new Date(validFrom);
        validFromDate.setDate(validFromDate.getDate() - 1);
        const validTo = validFromDate.toISOString().split('T')[0];
        
        const { error: deactivateError } = await supabase
          .from("buying_price_records")
          .update({ 
            status: "inactive",
            valid_to: validTo
          })
          .in("id", previousIds);

        if (deactivateError) throw deactivateError;
      }

      // Activate the current record and ensure valid_from is set
      const { error: activateError } = await supabase
        .from("buying_price_records")
        .update({ 
          status: "active",
          valid_from: validFrom,
          valid_to: null  // Clear valid_to when activating
        })
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
            .select("id, status")
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

              // Update invoice status to 'needs_review' if it was 'validated'
              // This ensures invoices are re-validated with the newly activated price record
              const validatedInvoices = invoices.filter((inv) => inv.status === "validated");
              if (validatedInvoices.length > 0) {
                const validatedInvoiceIds = validatedInvoices.map((inv) => inv.id);
                const { error: updateInvoicesError } = await supabase
                  .from("invoices")
                  .update({ status: "needs_review" })
                  .in("id", validatedInvoiceIds);

                if (updateInvoicesError) throw updateInvoicesError;
              }
            }
          }
        }
      }

      // Calculate valid_to date for deactivated records (day before valid_from)
      const validFromDate = new Date(validFrom);
      validFromDate.setDate(validFromDate.getDate() - 1);
      const validTo = validFromDate.toISOString().split('T')[0];

      // Update local state for both allRecords and records
      const updateRecord = (r: BuyingPriceRecord): BuyingPriceRecord => {
        if (r.id === record.id) {
          return { 
            ...r, 
            status: "active" as const,
            valid_from: validFrom,
            valid_to: null
          };
        }
        if (
          previousActive?.some((pa) => pa.id === r.id) &&
          r.status === "active"
        ) {
          return { 
            ...r, 
            status: "inactive" as const,
            valid_to: validTo
          };
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

  const handleStartEditPrice = (record: BuyingPriceRecord) => {
    setEditingPriceId(record.id);
    setEditingPriceValue(record.unit_price.toString());
  };

  const handleCancelEditPrice = () => {
    setEditingPriceId(null);
    setEditingPriceValue("");
  };

  const handleUpdatePrice = async (record: BuyingPriceRecord) => {
    if (!record.sku) {
      alert("Cannot update price: SKU is missing");
      return;
    }

    const newPrice = parseFloat(editingPriceValue);
    if (isNaN(newPrice) || newPrice < 0) {
      alert("Please enter a valid positive number");
      return;
    }

    setUpdatingPriceId(record.id);

    try {
      const supabase = createSupabaseBrowserClient();

      // Determine valid_from date: use today's date
      const updateDate = new Date().toISOString().split('T')[0]; // Today's date in YYYY-MM-DD format

      // If this is an active record, we need to deactivate other active records with the same SKU
      let previousActive: { id: string }[] | null = null;
      let validTo: string | null = null;

      if (record.status === "active") {
        // Find and deactivate ALL other active records with the same SKU
        console.log("  - - ", record.sku)
        const { data: prevActive, error: findError } = await supabase
          .from("buying_price_records")
          .select("id, status")
          .eq("sku", record.sku)
          .eq("product_name", record.product_name)
          .eq("status", "active")
          .neq("id", record.id);
        console.log(" - - - prevActive", prevActive)
        if (findError) throw findError;
        previousActive = prevActive;

        // Deactivate previous active records and set their valid_to to the day before the update date
        if (previousActive && previousActive.length > 0) {
          const previousIds = previousActive.map((r) => r.id);
          
          // Calculate valid_to date (day before updateDate)
          const updateDateObj = new Date(updateDate);
          updateDateObj.setDate(updateDateObj.getDate() - 1);
          validTo = updateDateObj.toISOString().split('T')[0];
          
          const { error: deactivateError } = await supabase
            .from("buying_price_records")
            .update({ 
              status: "inactive",
              valid_to: validTo
            })
            .in("id", previousIds);

          if (deactivateError) throw deactivateError;
        }
      }

      // Update the price record with new price and update valid_from date
      const { error: updateError } = await supabase
        .from("buying_price_records")
        .update({ 
          unit_price: newPrice,
          valid_from: updateDate,
          valid_to: null  // Clear valid_to when updating an active record
        })
        .eq("id", record.id);

      if (updateError) throw updateError;

      // Only update invoice_lines and invoice status if the price record status is 'active'
      // Inactive or need_review records don't affect invoice validation
      if (record.status === "active") {
        // Find all invoice_lines that match this price record by SKU or product_name
        // This matches the validation service logic: try SKU first, then product_name
        let invoiceLines: any[] = [];
        
        if (record.sku) {
          // First, try to find invoice lines by SKU
          const { data: skuLines, error: skuError } = await supabase
            .from("invoice_lines")
            .select("id, invoice_id, unit_price, currency, sku, product_name, status")
            .eq("sku", record.sku);
          
          if (skuError) throw skuError;
          if (skuLines) invoiceLines = skuLines;
        }
        
        if (!record.sku) {
          console.log("Price record has no SKU, cannot match invoice lines");
          // Update local state and return early
          const updateRecord = (r: BuyingPriceRecord): BuyingPriceRecord => {
            if (r.id === record.id) {
              return { ...r, unit_price: newPrice, valid_from: updateDate };
            }
            return r;
          };
          setAllRecords((prev) => prev.map(updateRecord));
          setRecords((prev) => prev.map(updateRecord));
          setEditingPriceId(null);
          setEditingPriceValue("");
          setUpdatingPriceId(null);
          return;
        }

        if (invoiceLines && invoiceLines.length > 0) {
          const invoiceIds = [...new Set(invoiceLines.map((line) => line.invoice_id))];

          // Check if invoices match the supplier
          const { data: invoices, error: invoicesError } = await supabase
            .from("invoices")
            .select("id, status")
            .in("id", invoiceIds)
            .eq("supplier_name", record.supplier_name);

          if (invoicesError) throw invoicesError;

          if (invoices && invoices.length > 0) {
            const matchingInvoiceIds = invoices.map((inv) => inv.id);
            const matchingLines = invoiceLines.filter((line) => 
              matchingInvoiceIds.includes(line.invoice_id)
            );

            // Compare prices and update status for each invoice line
            const linesToMatch: string[] = [];
            const linesToMismatch: string[] = [];

            for (const line of matchingLines) {
              // Compare prices (handle null/undefined and use small tolerance for floating point)
              const linePrice = line.unit_price ?? 0;
              const priceDiff = Math.abs(linePrice - newPrice);
              const tolerance = 0.01; // Small tolerance for floating point comparison

              if (priceDiff <= tolerance) {
                linesToMatch.push(line.id);
              } else {
                linesToMismatch.push(line.id);
              }
            }

            // Update invoice lines status
            if (linesToMatch.length > 0) {
              const { error: updateMatchError } = await supabase
                .from("invoice_lines")
                .update({ status: "match" })
                .in("id", linesToMatch);

              if (updateMatchError) {
                console.error("Error updating invoice lines to match:", updateMatchError);
                throw updateMatchError;
              }
              console.log(`Updated ${linesToMatch.length} invoice lines to 'match' status`);
            }

            if (linesToMismatch.length > 0) {
              const { error: updateMismatchError } = await supabase
                .from("invoice_lines")
                .update({ status: "mismatch" })
                .in("id", linesToMismatch);

              if (updateMismatchError) {
                console.error("Error updating invoice lines to mismatch:", updateMismatchError);
                throw updateMismatchError;
              }
              console.log(`Updated ${linesToMismatch.length} invoice lines to 'mismatch' status`);
            }

            // Update invoice status to 'needs_review' if it was 'validated'
            // This ensures invoices are re-validated with the newly updated price
            const validatedInvoices = invoices.filter((inv) => inv.status === "validated");
            if (validatedInvoices.length > 0) {
              const validatedInvoiceIds = validatedInvoices.map((inv) => inv.id);
              const { error: updateInvoicesError } = await supabase
                .from("invoices")
                .update({ status: "needs_review" })
                .in("id", validatedInvoiceIds);

              if (updateInvoicesError) {
                console.error("Error updating invoice status:", updateInvoicesError);
                throw updateInvoicesError;
              }

              console.log(`Updated ${validatedInvoiceIds.length} invoices from 'validated' to 'needs_review'`);
            }
          } else {
            console.log("No matching invoices found for supplier:", record.supplier_name);
          }
        } else {
          console.log("No invoice lines found with SKU:", record.sku);
        }
      } else {
        console.log("Price record status is not 'active', skipping invoice line updates");
      }

      // Update local state
      const updateRecord = (r: BuyingPriceRecord): BuyingPriceRecord => {
        if (r.id === record.id) {
          return { 
            ...r, 
            unit_price: newPrice, 
            valid_from: updateDate,
            valid_to: record.status === "active" ? null : r.valid_to  // Clear valid_to if active
          };
        }
        // Update deactivated records if this was an active record update
        if (
          record.status === "active" &&
          previousActive?.some((pa) => pa.id === r.id) &&
          r.status === "active"
        ) {
          return { 
            ...r, 
            status: "inactive" as const,
            valid_to: validTo
          };
        }
        return r;
      };

      setAllRecords((prev) => prev.map(updateRecord));
      setRecords((prev) => prev.map(updateRecord));
      setEditingPriceId(null);
      setEditingPriceValue("");
    } catch (err: any) {
      console.error("Error updating price:", err);
      alert(`Failed to update price: ${err.message}`);
    } finally {
      setUpdatingPriceId(null);
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
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
                    <div className="flex items-center gap-2">
                      <span>Status</span>
                      <div className="relative status-filter-container">
                        <button
                          className="flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-elevated transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowStatusFilter(!showStatusFilter);
                          }}
                        >
                          <Filter className="w-3.5 h-3.5" />
                          <ChevronDown className={cn(
                            "w-3 h-3 transition-transform",
                            showStatusFilter && "rotate-180"
                          )} />
                        </button>
                        {showStatusFilter && (
                          <div className="absolute left-0 top-full mt-1 w-40 bg-background border border-border rounded-lg shadow-xl z-50">
                            <div className="py-1 bg-background rounded-lg">
                              <button
                                onClick={() => {
                                  setStatusFilter("all");
                                  setShowStatusFilter(false);
                                }}
                                className={cn(
                                  "w-full text-left px-4 py-2 text-sm hover:bg-surface-elevated",
                                  statusFilter === "all" && "bg-surface-elevated font-medium"
                                )}
                              >
                                All
                              </button>
                              <button
                                onClick={() => {
                                  setStatusFilter("active");
                                  setShowStatusFilter(false);
                                }}
                                className={cn(
                                  "w-full text-left px-4 py-2 text-sm hover:bg-surface-elevated",
                                  statusFilter === "active" && "bg-surface-elevated font-medium"
                                )}
                              >
                                Active
                              </button>
                              <button
                                onClick={() => {
                                  setStatusFilter("need_review");
                                  setShowStatusFilter(false);
                                }}
                                className={cn(
                                  "w-full text-left px-4 py-2 text-sm hover:bg-surface-elevated transition-colors",
                                  statusFilter === "need_review" && "bg-surface-elevated font-medium"
                                )}
                              >
                                Need Review
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
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
                        {searchTerm.trim() || statusFilter !== "all"
                          ? "No price records match your filters"
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
                          {editingPriceId === record.id ? (
                            <div className="flex items-center gap-2">
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={editingPriceValue}
                                onChange={(e) => setEditingPriceValue(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    handleUpdatePrice(record);
                                  } else if (e.key === "Escape") {
                                    handleCancelEditPrice();
                                  }
                                }}
                                className="w-24 px-2 py-1 bg-surface border border-border rounded text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                                autoFocus
                                disabled={updatingPriceId === record.id}
                              />
                              <span className="text-text-tertiary text-xs">
                                {record.currency}
                              </span>
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleUpdatePrice(record)}
                                  disabled={updatingPriceId === record.id}
                                  className={cn(
                                    "p-1 rounded hover:bg-surface-elevated transition-colors",
                                    updatingPriceId === record.id && "opacity-50 cursor-not-allowed"
                                  )}
                                  title="Save"
                                >
                                  {updatingPriceId === record.id ? (
                                    <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                                  ) : (
                                    <Save className="w-4 h-4 text-green-500" />
                                  )}
                                </button>
                                <button
                                  onClick={handleCancelEditPrice}
                                  disabled={updatingPriceId === record.id}
                                  className={cn(
                                    "p-1 rounded hover:bg-surface-elevated transition-colors",
                                    updatingPriceId === record.id && "opacity-50 cursor-not-allowed"
                                  )}
                                  title="Cancel"
                                >
                                  <X className="w-4 h-4 text-red-500" />
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 group">
                              <span>{formatCurrency(record.unit_price, record.currency)}</span>
                              <button
                                onClick={() => handleStartEditPrice(record)}
                                className="opacity-50 group-hover:opacity-100 p-1 rounded-md border border-gray-700 hover:bg-surface-elevated transition-all"
                                title="Edit price"
                              >
                                <Edit2 className="w-3.5 h-3.5 text-text-tertiary hover:text-primary" />
                              </button>
                            </div>
                          )}
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

