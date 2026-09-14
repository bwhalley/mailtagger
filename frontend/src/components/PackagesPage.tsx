import { Package, RefreshCw, ShoppingBag } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  getCommerceSummary,
  getOpenOrders,
  getActiveShipments,
  getShipmentsByStatus
} from "../api";
import type { ApiOrder, ApiShipment, CommerceSummary } from "../types";
import { OrderCard } from "./OrderCard";
import { ShipmentCard } from "./ShipmentCard";

interface PackagesPageProps {
  onNavigate: (path: string) => void;
}

type Tab = "shipments" | "orders";

export function PackagesPage({ onNavigate }: PackagesPageProps) {
  const [tab, setTab] = useState<Tab>("shipments");
  const [summary, setSummary] = useState<CommerceSummary | null>(null);
  const [outForDelivery, setOutForDelivery] = useState<ApiShipment[]>([]);
  const [inTransit, setInTransit] = useState<ApiShipment[]>([]);
  const [delivered, setDelivered] = useState<ApiShipment[]>([]);
  const [openOrders, setOpenOrders] = useState<ApiOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, ood, active, deliveredList, orders] = await Promise.all([
        getCommerceSummary(),
        getShipmentsByStatus("out_for_delivery", 20),
        getActiveShipments(50),
        getShipmentsByStatus("delivered", 15),
        getOpenOrders(20)
      ]);
      setSummary(summaryData);
      setOutForDelivery(ood);
      setInTransit(
        active.filter((s) => s.status === "shipped" || s.status === "in_transit")
      );
      setDelivered(deliveredList);
      setOpenOrders(orders);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load packages.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-20 border-b border-border bg-background/90 backdrop-blur">
        <div className="container flex items-center justify-between py-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onNavigate("/")}
              className="rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
            >
              Inbox
            </button>
            <Package className="h-5 w-5 text-primary" />
            <h1 className="font-display text-lg font-semibold">Commerce</h1>
          </div>
          <button
            type="button"
            onClick={refresh}
            className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1.5 text-xs font-medium text-muted-foreground"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </header>

      <main className="container py-6">
        <section className="mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">In transit</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.in_transit ?? "-"}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Out for delivery</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.out_for_delivery ?? "-"}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Open orders</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.orders_open ?? "-"}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Delivered (30d)</p>
            <p className="mt-2 text-2xl font-display font-semibold">
              {summary?.delivered_recent ?? "-"}
            </p>
          </div>
        </section>

        <div className="mb-4 flex gap-2">
          <button
            type="button"
            onClick={() => setTab("shipments")}
            className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === "shipments"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            <Package className="h-3.5 w-3.5" />
            Shipments
          </button>
          <button
            type="button"
            onClick={() => setTab("orders")}
            className={`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium ${
              tab === "orders"
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground"
            }`}
          >
            <ShoppingBag className="h-3.5 w-3.5" />
            Orders
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-md border border-lane-urgent/30 bg-lane-urgent-soft px-3 py-2 text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
            Loading...
          </div>
        ) : tab === "shipments" ? (
          <div className="space-y-6">
            {outForDelivery.length > 0 && (
              <section className="space-y-3">
                <h2 className="font-display text-base font-semibold">Out for delivery</h2>
                <div className="space-y-3">
                  {outForDelivery.map((shipment) => (
                    <ShipmentCard key={shipment.id} shipment={shipment} highlight />
                  ))}
                </div>
              </section>
            )}
            {inTransit.length > 0 && (
              <section className="space-y-3">
                <h2 className="font-display text-base font-semibold">In transit</h2>
                <div className="space-y-3">
                  {inTransit.map((shipment) => (
                    <ShipmentCard key={shipment.id} shipment={shipment} />
                  ))}
                </div>
              </section>
            )}
            {delivered.length > 0 && (
              <section className="space-y-3">
                <h2 className="font-display text-base font-semibold">Recently delivered</h2>
                <div className="space-y-3">
                  {delivered.map((shipment) => (
                    <ShipmentCard key={shipment.id} shipment={shipment} />
                  ))}
                </div>
              </section>
            )}
            {outForDelivery.length === 0 && inTransit.length === 0 && delivered.length === 0 && (
              <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
                No shipments tracked yet.
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <h2 className="font-display text-base font-semibold">Orders awaiting shipment</h2>
            {openOrders.length === 0 ? (
              <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
                No open orders without shipments.
              </div>
            ) : (
              openOrders.map((order) => <OrderCard key={order.id} order={order} />)
            )}
          </div>
        )}
      </main>
    </div>
  );
}
