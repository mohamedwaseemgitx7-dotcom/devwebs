import { AlertTriangle, Minus, PackageOpen, Plus, Star } from "lucide-react";
import type { ReactNode } from "react";

export function Stars({ rating, count }: { rating: number; count?: number }) {
  const full = Math.round(rating);
  return (
    <div className="flex items-center gap-1.5 text-xs text-muted">
      <span className="flex" role="img" aria-label={`Rated ${rating.toFixed(1)} out of 5`}>
        {[1, 2, 3, 4, 5].map((i) => (
          <Star key={i} aria-hidden="true" className={`h-3.5 w-3.5 ${i <= full ? "fill-star text-star" : "fill-line text-line"}`} />
        ))}
      </span>
      {count !== undefined && <span>{count === 1 ? "1 Review" : `${count.toLocaleString("en-IN")} Reviews`}</span>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-16 text-muted">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-16 text-center">
      <PackageOpen className="h-10 w-10 text-brand-500" aria-hidden="true" />
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <div className="max-w-md text-sm text-muted">{children}</div>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="card flex flex-col items-center gap-3 border-red-200 bg-red-50 px-6 py-12 text-center">
      <AlertTriangle className="h-8 w-8 text-danger" aria-hidden="true" />
      <p className="text-sm">{message}</p>
      {onRetry && (
        <button type="button" className="btn-outline" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Alert({ kind = "error", children }: { kind?: "error" | "success" | "info"; children: ReactNode }) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-brand-200 bg-brand-50 text-brand-800",
    info: "border-line bg-white text-ink",
  }[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>
      {children}
    </div>
  );
}

export function QuantityStepper({
  value,
  max,
  onChange,
  disabled,
  label,
}: {
  value: number;
  max: number;
  onChange: (v: number) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <div className="inline-flex items-center rounded-lg border border-line bg-white" role="group" aria-label={label}>
      <button type="button" className="p-2 disabled:opacity-40" aria-label="Decrease quantity" disabled={disabled || value <= 1}
        onClick={() => onChange(value - 1)}>
        <Minus className="h-4 w-4" aria-hidden="true" />
      </button>
      <span className="min-w-8 text-center text-sm font-medium" aria-live="polite">{value}</span>
      <button type="button" className="p-2 disabled:opacity-40" aria-label="Increase quantity" disabled={disabled || value >= max}
        onClick={() => onChange(value + 1)}>
        <Plus className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

export function ProductImage({ src, alt, className = "" }: { src?: string | null; alt: string; className?: string }) {
  return (
    <img
      src={src ?? "/favicon.svg"}
      alt={alt}
      loading="lazy"
      decoding="async"
      width={400}
      height={300}
      className={`aspect-[4/3] w-full object-contain ${className}`}
    />
  );
}
