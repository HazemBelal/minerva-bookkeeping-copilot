export function ScreenshotViewer({
  url,
  label,
}: {
  url: string | null;
  label: string | null;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2">
      {url ? (
        <>
          <img src={url} alt={label ?? "Current page"} className="w-full rounded" />
          <p className="mt-1 text-[11px] text-slate-500">{label}</p>
        </>
      ) : (
        <div className="flex h-40 items-center justify-center text-xs text-slate-400">
          The browser view appears here once the agent opens a page.
        </div>
      )}
    </div>
  );
}
