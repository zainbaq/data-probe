"use client";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="p-8 max-w-xl mx-auto mt-16 text-center">
      <h2 className="text-xl font-bold text-slate-900 mb-2">Something went wrong</h2>
      <p className="text-slate-500 text-sm mb-6">{error.message}</p>
      <button
        onClick={reset}
        className="bg-accent-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-700 transition-colors"
      >
        Try again
      </button>
    </div>
  );
}
