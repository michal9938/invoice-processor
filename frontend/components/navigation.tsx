"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, CheckCircle2, Menu, X, AlertTriangle, Bell, DollarSign } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Invoices", href: "/invoices", icon: FileText },
  { name: "NeedReview", href: "/review", icon: AlertTriangle },
  { name: "Approvals", href: "/approvals", icon: CheckCircle2 },
  {name : "Price Records", href: "/pricerecords", icon: DollarSign },
];

export function Navigation() {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationCount, setNotificationCount] = useState(0);

  // useEffect(() => {
  //   async function fetchNotificationCount() {
  //     try {
  //       const supabase = createSupabaseBrowserClient();
        
  //       // Count invoices that need review
  //       const { count, error } = await supabase
  //         .from("invoices")
  //         .select("*", { count: "exact", head: true })
  //         .eq("status", "needs_review");

  //       if (error) throw error;
  //       setNotificationCount(count || 0);
  //     } catch (err) {
  //       console.error("Error fetching notification count:", err);
  //     }
  //   }

  //   fetchNotificationCount();
    
  //   // Refresh every 30 seconds
  //   const interval = setInterval(fetchNotificationCount, 30000);
  //   return () => clearInterval(interval);
  // }, []);

  // // Close notifications dropdown when clicking outside
  // useEffect(() => {
  //   function handleClickOutside(event: MouseEvent) {
  //     const target = event.target as HTMLElement;
  //     if (notificationsOpen && !target.closest('.notifications-container')) {
  //       setNotificationsOpen(false);
  //     }
  //   }

  //   if (notificationsOpen) {
  //     document.addEventListener('mousedown', handleClickOutside);
  //     return () => document.removeEventListener('mousedown', handleClickOutside);
  //   }
  // }, [notificationsOpen]);

  return (
    <nav className="sticky top-0 z-50 glass-effect border-b border-border shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo */}
          <div className="flex items-center">
            <Link href="/" className="flex items-center space-x-2 group">
              <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center shadow-glow">
                <FileText className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold gradient-text hidden sm:block">
                Invoice Control
              </span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-1">
            {navigation.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    "flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-all duration-200",
                    isActive
                      ? "bg-gradient-to-r from-[#06b6d4] to-[#0891b2] text-white shadow-md"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated"
                  )}
                >
                  <item.icon className="w-4 h-4" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
            
            {/* Notifications Button */}
            <div className="relative ml-2 notifications-container">
              <button
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="relative p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-surface-elevated transition-all duration-200"
              >
                <Bell className="w-5 h-5" />
                {notificationCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse-slow">
                    {notificationCount > 9 ? "9+" : notificationCount}
                  </span>
                )}
              </button>
              
              {/* Notifications Dropdown */}
              {notificationsOpen && (
                <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl border border-border shadow-xl z-[9999] animate-fade-in notifications-container">
                  <div className="p-4 border-b border-border">
                    <h3 className="font-semibold text-text-primary">Notifications</h3>
                  </div>
                  <div className="max-h-96 overflow-y-auto">
                    {notificationCount > 0 ? (
                      <div className="p-4">
                        <Link
                          href="/review"
                          onClick={() => setNotificationsOpen(false)}
                          className="block p-3 rounded-lg bg-orange-50 border border-orange-200 hover:bg-orange-100 transition-colors"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <AlertTriangle className="w-4 h-4 text-orange-600" />
                            <span className="font-medium text-text-primary">
                              {notificationCount} invoice{notificationCount !== 1 ? "s" : ""} need review
                            </span>
                          </div>
                          <p className="text-sm text-text-secondary">
                            Click to review invoices requiring manual checking
                          </p>
                        </Link>
                      </div>
                    ) : (
                      <div className="p-8 text-center">
                        <Bell className="w-12 h-12 text-text-muted mx-auto mb-2" />
                        <p className="text-text-secondary">No new notifications</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Mobile menu button and notifications */}
          <div className="md:hidden flex items-center gap-2">
            {/* Notifications Button - Mobile */}
            <div className="relative notifications-container">
              <button
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="relative p-2 rounded-lg text-text-primary hover:bg-surface-elevated transition-colors"
              >
                <Bell className="w-6 h-6" />
                {notificationCount > 0 && (
                  <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse-slow">
                    {notificationCount > 9 ? "9+" : notificationCount}
                  </span>
                )}
              </button>
              
              {/* Notifications Dropdown - Mobile */}
              {notificationsOpen && (
                <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl border border-border shadow-xl z-[9999] animate-fade-in notifications-container">
                  <div className="p-4 border-b border-border">
                    <h3 className="font-semibold text-text-primary">Notifications</h3>
                  </div>
                  <div className="max-h-96 overflow-y-auto">
                    {notificationCount > 0 ? (
                      <div className="p-4">
                        <Link
                          href="/review"
                          onClick={() => setNotificationsOpen(false)}
                          className="block p-3 rounded-lg bg-orange-50 border border-orange-200 hover:bg-orange-100 transition-colors"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <AlertTriangle className="w-4 h-4 text-orange-600" />
                            <span className="font-medium text-text-primary">
                              {notificationCount} invoice{notificationCount !== 1 ? "s" : ""} need review
                            </span>
                          </div>
                          <p className="text-sm text-text-secondary">
                            Click to review invoices requiring manual checking
                          </p>
                        </Link>
                      </div>
                    ) : (
                      <div className="p-8 text-center">
                        <Bell className="w-12 h-12 text-text-muted mx-auto mb-2" />
                        <p className="text-text-secondary">No new notifications</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-text-primary hover:bg-surface-elevated transition-colors"
            >
              {mobileMenuOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {mobileMenuOpen && (
          <div className="md:hidden py-4 space-y-2 animate-fade-in">
            
            {navigation.map((item) => {
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.name} 
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    "flex items-center space-x-2 px-4 py-3 rounded-lg font-medium transition-all duration-200",
                    isActive
                      ? "bg-gradient-to-r from-[#06b6d4] to-[#0891b2] text-white shadow-md"
                      : "text-text-secondary hover:text-text-primary hover:bg-surface-elevated"
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </nav>
  );
}

