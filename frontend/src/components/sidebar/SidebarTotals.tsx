import { compactNumber, formatBytes } from "../../lib/format";

export function SidebarTotals({
  codeLines,
  diskBytes,
}: {
  codeLines: number;
  diskBytes: number;
}) {
  return (
    <div className="sidebar-totals">
      <div>
        <span>代码行</span>
        <strong>{compactNumber(codeLines)}</strong>
      </div>
      <div>
        <span>磁盘</span>
        <strong>{formatBytes(diskBytes)}</strong>
      </div>
    </div>
  );
}
