"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  XCircle,
  FileText,
  Download,
  Eye,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Invoice {
  id: string;
  supplier_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string | null;
  subtotal_amount: number | null;
  tax_amount: number | null;
  total_amount: number | null;
  status: string;
  storage_path: string | null;
  created_at: string;
  frieght_amount: number | null;
}

interface InvoiceLine {
  id: string;
  line_no: number;
  sku: string | null;
  product_name: string | null;
  description: string | null;
  quantity: number | null;
  unit: string | null;
  unit_price: number | null;
  discount: number | null;
  discount_total: number | null;
  net_amount: number | null;
  vat_percentage: number | null;
  line_total: number | null;
  currency: string | null;
  status: string | null;
}

type Currency = 'DKK' | 'EUR';

export default function InvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const invoiceId = params.id as string;

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [lines, setLines] = useState<InvoiceLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [approvingLineId, setApprovingLineId] = useState<string | null>(null);
  const [currencyType, setCurrencyType] = useState<Currency>('DKK');

  useEffect(() => {
    async function fetchInvoiceDetails() {
      try {
        const supabase = createSupabaseBrowserClient();

        // Fetch invoice
        const { data: invoiceData, error: invoiceError } = await supabase
          .from("invoices")
          .select("*")
          .eq("id", invoiceId)
          .single();

        if (invoiceError) throw invoiceError;
        setInvoice(invoiceData);

        // Fetch invoice lines with status
        const { data: linesData, error: linesError } = await supabase
          .from("invoice_lines")
          .select("*")
          .eq("invoice_id", invoiceId)
          .order("line_no", { ascending: true });

        if (linesError) throw linesError;
        setLines(linesData || []);
      } catch (err: any) {
        console.error("Error fetching invoice details:", err);
      } finally {
        setLoading(false);
      }
    }

    if (invoiceId) {
      fetchInvoiceDetails();
    }
  }, [invoiceId]);

  const handleApprove = async () => {
    if (!invoice) return;

    try {
      const supabase = createSupabaseBrowserClient();

      const { error } = await supabase
        .from("invoices")
        .update({ status: "closed" })
        .eq("id", invoice.id);

      if (error) throw error;

      router.push("/approvals");
    } catch (err: any) {
      console.error("Error approving invoice:", err);
      alert(`Failed to approve invoice: ${err.message}`);
    }
  };

  const handleDownload = async () => {
    if (!invoice?.storage_path) return;

    try {
      const supabase = createSupabaseBrowserClient();
      const { data, error } = await supabase.storage
        .from("pdfs")
        .download(invoice.storage_path);

      if (error) throw error;

      const url = window.URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = invoice.storage_path.split("/").pop() || "invoice.pdf";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      console.error("Error downloading file:", err);
      alert(`Failed to download file: ${err.message}`);
    }
  };

  const handleViewPDF = async () => {
    if (!invoice?.storage_path) return;

    const url = `https://xcnwbfmoxqacpdscgaef.supabase.co/storage/v1/object/public/pdfs/${invoice.storage_path}`;
    window.open(url, "_blank");
  };

  const handleApprovePriceFromLine = async (line: InvoiceLine) => {
    if (!line.sku || !invoice?.supplier_name) {
      alert("Cannot approve: SKU or supplier information is missing");
      return;
    }

    setApprovingLineId(line.id);

    try {
      const supabase = createSupabaseBrowserClient();

      // Find the latest active or need_review buying_price_record for this SKU and supplier
      const { data: priceRecords, error: findError } = await supabase
        .from("buying_price_records")
        .select("*")
        .eq("supplier_name", invoice.supplier_name)
        .eq("sku", line.sku)
        .in("status", ["active", "need_review"])
        .order("created_at", { ascending: false })
        .limit(1);

      if (findError) throw findError;

      if (!priceRecords || priceRecords.length === 0) {
        alert("No price record found for this SKU. Please create one first.");
        return;
      }

      const priceRecord = priceRecords[0];

      // If it's already active, just update the invoice line
      if (priceRecord.status === "active") {
        const { error: updateLineError } = await supabase
          .from("invoice_lines")
          .update({ status: "match" })
          .eq("id", line.id);

        if (updateLineError) throw updateLineError;

        // Update local state
        setLines((prev) =>
          prev.map((l) => (l.id === line.id ? { ...l, status: "match" } : l))
        );
        return;
      }

      // If it's need_review, activate it (which will also update invoice_lines)
      // Determine valid_from date: use invoice date if available, otherwise use price record's valid_from or today
      let validFrom: string;
      if (invoice.invoice_date) {
        // Use invoice date
        validFrom = invoice.invoice_date.split('T')[0]; // Extract date part if it's a datetime
      } else if (priceRecord.valid_from) {
        // Use existing valid_from from price record
        validFrom = priceRecord.valid_from.split('T')[0];
      } else {
        // Use today's date as fallback
        validFrom = new Date().toISOString().split('T')[0];
      }

      // First, find and deactivate ALL previous active records with the same SKU
      const { data: previousActive, error: prevError } = await supabase
        .from("buying_price_records")
        .select("id")
        .eq("supplier_name", invoice.supplier_name)
        .eq("sku", line.sku)
        .eq("status", "active")
        .neq("id", priceRecord.id);

      if (prevError) throw prevError;

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

      // Activate the current record and set valid_from properly
      const { error: activateError } = await supabase
        .from("buying_price_records")
        .update({ 
          status: "active",
          valid_from: validFrom,
          valid_to: null  // Clear valid_to when activating
        })
        .eq("id", priceRecord.id);

      if (activateError) throw activateError;

      // Update the current invoice line status to 'match'
      const { error: updateCurrentLineError } = await supabase
        .from("invoice_lines")
        .update({ status: "match" })
        .eq("id", line.id);

      if (updateCurrentLineError) throw updateCurrentLineError;

      // Find and update related invoice_lines with same SKU and status 'created_price_record'
      const { data: invoiceLines, error: linesError } = await supabase
        .from("invoice_lines")
        .select("id, invoice_id")
        .eq("sku", line.sku)
        .eq("status", "created_price_record")
        .neq("id", line.id); // Exclude the current line since we already updated it

      if (linesError) throw linesError;

      // Get supplier_name from invoices to match
      if (invoiceLines && invoiceLines.length > 0) {
        const invoiceIds = [...new Set(invoiceLines.map((l) => l.invoice_id))];

        // Check if invoices match the supplier
        const { data: invoices, error: invoicesError } = await supabase
          .from("invoices")
          .select("id")
          .in("id", invoiceIds)
          .eq("supplier_name", invoice.supplier_name);

        if (invoicesError) throw invoicesError;

        if (invoices && invoices.length > 0) {
          const matchingInvoiceIds = invoices.map((inv) => inv.id);
          const matchingLineIds = invoiceLines
            .filter((l) => matchingInvoiceIds.includes(l.invoice_id))
            .map((l) => l.id);

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

      // Update local state
      setLines((prev) =>
        prev.map((l) => (l.id === line.id ? { ...l, status: "match" } : l))
      );
    } catch (err: any) {
      console.error("Error approving price from invoice line:", err);
      alert(`Failed to approve price: ${err.message}`);
    } finally {
      setApprovingLineId(null);
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
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

  const getValidationStatus = (line: InvoiceLine) => {
    if (!line.status) return null;

    return {
      status: line.status,
    };
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

  if (!invoice) {
    return (
      <div className="min-h-screen bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center py-12">
            <p className="text-text-secondary text-lg">Invoice not found</p>
            <Link
              href="/invoices"
              className="mt-4 inline-block text-primary hover:underline"
            >
              Back to Invoices
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-8xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8 animate-fade-in">
          <Link
            href="/invoices"
            className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Invoices
          </Link>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold gradient-text mb-2">
                {invoice.supplier_name || "Unknown Supplier"}
              </h1>
              <p className="text-text-secondary">
                Invoice #{invoice.invoice_number || "N/A"} •{" "}
                {formatDate(invoice.invoice_date)}
              </p>
            </div>
            <div className="flex gap-3">
              {invoice.storage_path && (
                <button
                  onClick={handleDownload}
                  className="px-4 py-2 bg-surface border border-border rounded-lg hover:bg-surface-elevated transition-colors flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
              )}
              {
                <button
                  onClick = {handleViewPDF}
                  className="px-4 py-2 bg-surface border border-border rounded-lg hover:bg-surface-elevated transition-colors flex items-center gap-2"
                >
                  <Eye className="w-4 h-4" />
                  View PDF
                </button>
              }
              {/* {invoice.status !== "closed" && (
                <button
                  onClick={handleApprove}
                  className="px-6 py-2 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg font-medium hover:shadow-lg transition-all duration-200 flex items-center gap-2"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Approve Invoice
                </button>
              )} */}
            </div>
          </div>
        </div>

        {/* Invoice Summary */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-surface rounded-xl p-6 border border-border hover-lift">
            <h3 className="text-sm font-medium text-text-tertiary mb-2">
              Subtotal
            </h3>
            <p className="text-2xl font-bold text-text-primary">
              {formatCurrency(invoice.subtotal_amount, invoice.currency)}
            </p>
          </div>
          <div className="bg-surface rounded-xl p-6 border border-border hover-lift">
            <h3 className="text-sm font-medium text-text-tertiary mb-2">
              Tax
            </h3>
            <p className="text-2xl font-bold text-text-primary">
              {formatCurrency(invoice.tax_amount, invoice.currency)}
            </p>
          </div>
          <div className="bg-surface rounded-xl p-6 border border-border hover-lift">
            <h3 className="text-sm font-medium text-text-tertiary mb-2">
              Frieght
            </h3>
            <p className="text-2xl font-bold text-text-primary">
              {formatCurrency(invoice.frieght_amount, invoice.currency)}
            </p>
          </div>
          <div className="bg-gradient-to-br from-[#06b6d4] to-[#0891b2] rounded-xl p-6 text-white hover-lift">
            <h3 className="text-sm font-medium opacity-90 mb-2">Total</h3>
            <p className="text-2xl font-bold">
              {formatCurrency(invoice.total_amount, invoice.currency)}
            </p>
          </div>
        </div>

        {/* Invoice Lines */}
        <div className="bg-surface rounded-xl border border-border overflow-hidden">
          <div className="p-6 border-b border-border">
            <h2 className="text-2xl font-bold text-text-primary">
              Invoice Lines
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-surface-elevated">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Line
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    SKU
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Product
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Qty
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Unit
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Unit Price
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Discount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    VAT %
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Net Amount
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-text-tertiary uppercase tracking-wider">
                    Total
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
                {lines.map((line, index) => {
                  const validation = getValidationStatus(line);
                  const hasIssue =
                    validation &&
                    (validation.status === "mismatch" ||
                      validation.status === "no_match");

                  return (
                    <tr
                      key={line.id}
                      className={cn(
                        "hover:bg-surface-elevated transition-colors animate-fade-in",
                        hasIssue && "bg-orange-50/50"
                      )}
                      style={{ animationDelay: `${index * 0.05}s` }}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-primary">
                        {line.line_no}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {line.sku || "—"}
                      </td>
                      <td className="px-6 py-4 text-sm text-text-primary">
                        <div>
                          <div className="font-medium">
                            {line.product_name || "—"}
                          </div>
                          {line.description && (
                            <div className="text-text-tertiary text-xs mt-1">
                              {line.description}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {line.quantity || "—"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {line.unit || "—"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {formatCurrency(line.unit_price, invoice.currency)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {line.discount ? `${line.discount}%` : "—"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {line.vat_percentage !== null ? `${line.vat_percentage}%` : "—"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-text-secondary">
                        {line.net_amount ? formatCurrency(line.net_amount, invoice.currency) : "—"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-text-primary">
                        {formatCurrency(line.line_total, invoice.currency)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {validation ? (
                          <div className="flex items-center gap-2">
                            {validation.status === "match" && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700 border border-green-200">
                                <CheckCircle2 className="w-3 h-3" />
                                Match
                              </span>
                            )}
                            {validation.status === "mismatch" && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700 border border-red-200">
                                <AlertCircle className="w-3 h-3" />
                                Mismatch
                              </span>
                            )}
                            {validation.status === "no_match" && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700 border border-yellow-200">
                                <XCircle className="w-3 h-3" />
                                No Match
                              </span>
                            )}
                            {validation.status === "created_price_record" && (
                              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700 border border-blue-200">
                                <FileText className="w-3 h-3" />
                                New Price
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-text-muted">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {validation?.status === "created_price_record" && (
                          <button
                            onClick={() => handleApprovePriceFromLine(line)}
                            disabled={approvingLineId === line.id || !line.sku}
                            className={cn(
                              "px-4 py-1.5 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg text-xs font-medium hover:shadow-lg transition-all duration-200 flex items-center gap-1.5",
                              (approvingLineId === line.id || !line.sku) &&
                                "opacity-50 cursor-not-allowed"
                            )}
                          >
                            {approvingLineId === line.id ? (
                              <>
                                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                Approving...
                              </>
                            ) : (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Approve Price
                              </>
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

