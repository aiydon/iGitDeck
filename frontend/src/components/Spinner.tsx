export function Spinner({ label = "加载中" }: { label?: string }) {
  return (
    <span className="spinner" role="status" aria-label={label}>
      <span className="spinner-ring" />
    </span>
  );
}
