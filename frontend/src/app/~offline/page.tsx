export default function OfflinePage() {
  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="text-center">
        <h1 className="text-xl font-bold text-slate-800">You&apos;re offline</h1>
        <p className="mt-2 text-sm text-slate-500">
          This page isn&apos;t available offline. Please check your connection and try again.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    </main>
  );
}
