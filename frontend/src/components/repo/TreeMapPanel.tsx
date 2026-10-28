import type { EChartsOption } from "echarts";
import { useMemo, useState } from "react";

import { api } from "../../api/client";
import type { TreeNode } from "../../api/client";
import {
  compactNumber,
  formatBytes,
  formatNumber,
  shortSha,
} from "../../lib/format";
import { useRequest } from "../../lib/hooks";
import { EChart } from "../EChart";
import { EmptyState } from "../EmptyState";
import { FileIcon } from "../icons";
import { Spinner } from "../Spinner";

type Weighting = "size" | "files";

const WEIGHTINGS = [
  { value: "size", label: "按大小" },
  { value: "files", label: "按文件数" },
] as const;

const TOOLTIP_STYLE = {
  backgroundColor: "#18201a",
  borderColor: "rgba(255,255,255,0.14)",
  borderWidth: 1,
  textStyle: { color: "#eef2e9", fontSize: 12 },
} as const;

/** Hex palette: zrender's hsl() parsing is unreliable across versions. */
const SIBLING_COLORS = [
  "#3f9f74",
  "#4a86c8",
  "#c08a3e",
  "#8a63c9",
  "#7aa63f",
  "#c25f92",
  "#3fa3a3",
  "#5f74c9",
];
const DEPTH_OPACITY = [1, 0.78, 0.62, 0.5];

interface TreemapDatum {
  id: string;
  name: string;
  value: number;
  path: string;
  size: number;
  files: number;
  itemStyle: { color: string };
  children?: TreemapDatum[];
}

function familyColor(rootIndex: number, depth: number, index: number): string {
  const hex = SIBLING_COLORS[rootIndex % SIBLING_COLORS.length].slice(1);
  const red = Number.parseInt(hex.slice(0, 2), 16);
  const green = Number.parseInt(hex.slice(2, 4), 16);
  const blue = Number.parseInt(hex.slice(4, 6), 16);
  // A top-level directory owns one hue; siblings and deeper levels only vary
  // opacity, so the eye can still group a subtree like WizTree does.
  const base = DEPTH_OPACITY[Math.min(depth, DEPTH_OPACITY.length - 1)];
  const alpha = Math.max(0.32, base - (index % 3) * 0.07);
  return alpha === 1 ? `#${hex}` : `rgba(${red}, ${green}, ${blue}, ${alpha.toFixed(2)})`;
}

function buildData(
  nodes: TreeNode[],
  weighting: Weighting,
  depth = 0,
  rootIndex = 0,
): TreemapDatum[] {
  const weightOf = (node: TreeNode) =>
    weighting === "size" ? node.size : node.files;
  const sorted = [...nodes].sort((left, right) => weightOf(right) - weightOf(left));
  const total = sorted.reduce((sum, node) => sum + weightOf(node), 0);
  // Tiny directories otherwise paint a stray square a few pixels wide.
  const threshold = Math.max(1, total * 0.003);
  const kept = sorted.filter((node) => weightOf(node) >= threshold);
  const rest = sorted.filter((node) => weightOf(node) < threshold);

  const rows: (TreeNode & { synthetic?: boolean })[] = [...kept];
  if (rest.length > 0) {
    rows.push({
      name: `其他 ${rest.length} 项`,
      path: "",
      synthetic: true,
      size: rest.reduce((sum, node) => sum + node.size, 0),
      files: rest.reduce((sum, node) => sum + node.files, 0),
      children: [],
    });
  }

  return rows.map((node, index) => {
    const family = depth === 0 ? index : rootIndex;
    const synthetic = "synthetic" in node && node.synthetic;
    return {
      id: node.path || `rest-${depth}-${rootIndex}`,
      name: node.name,
      value: weightOf(node),
      path: node.path,
      size: node.size,
      files: node.files,
      itemStyle: {
        color: synthetic ? "rgba(148, 158, 148, 0.45)" : familyColor(family, depth, index),
      },
      children:
        (node.children ?? []).length > 0
          ? buildData(node.children ?? [], weighting, depth + 1, family)
          : undefined,
    };
  });
}

const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char] ?? char);
}

function isTreemapDatum(value: unknown): value is TreemapDatum {
  return (
    typeof value === "object" &&
    value !== null &&
    "path" in value &&
    typeof value.path === "string" &&
    "name" in value &&
    typeof value.name === "string" &&
    "size" in value &&
    typeof value.size === "number" &&
    "files" in value &&
    typeof value.files === "number"
  );
}

function datumOf(params: unknown): TreemapDatum | undefined {
  if (typeof params !== "object" || params === null || !("data" in params)) {
    return undefined;
  }
  return isTreemapDatum(params.data) ? params.data : undefined;
}

function treemapOption(nodes: TreeNode[], weighting: Weighting): EChartsOption {
  return {
    backgroundColor: "transparent",
    animationDuration: 260,
    tooltip: {
      trigger: "item",
      confine: true,
      ...TOOLTIP_STYLE,
      formatter: (params: unknown) => {
        const datum = datumOf(params);
        if (!datum) return "";
        return [
          `<strong>${escapeHtml(datum.name)}</strong>`,
          escapeHtml(datum.path),
          `${formatBytes(datum.size)} · ${formatNumber(datum.files)} 个文件`,
        ].join("<br/>");
      },
    },
    series: [
      {
        type: "treemap",
        name: "全部",
        data: buildData(nodes, weighting),
        left: 0,
        right: 0,
        top: 0,
        bottom: 0,
        roam: false,
        // Two levels are shown at once; clicking does not zoom, so there is no
        // navigation state to explain (or forget to reset).
        nodeClick: false,
        leafDepth: 2,
        breadcrumb: { show: false },
        upperLabel: {
          show: true,
          height: 22,
          color: "#f2f7f0",
          fontSize: 11,
          formatter: (params: unknown) => {
            const datum = datumOf(params);
            if (!datum) return "";
            const amount =
              weighting === "size"
                ? formatBytes(datum.size)
                : `${compactNumber(datum.files)} 个文件`;
            return `${datum.name} · ${amount}`;
          },
        },
        itemStyle: {
          borderColor: "#0e120f",
          gapWidth: 2,
          borderRadius: 3,
        },
        label: {
          show: true,
          color: "#f7faf5",
          fontSize: 11,
          lineHeight: 15,
          textShadowColor: "rgba(0,0,0,0.45)",
          textShadowBlur: 2,
          formatter: (params: unknown) => {
            const datum = datumOf(params);
            if (!datum) return "";
            const amount =
              weighting === "size"
                ? formatBytes(datum.size)
                : `${compactNumber(datum.files)} 个文件`;
            return `${datum.name}\n${amount}`;
          },
        },
        emphasis: {
          itemStyle: {
            borderColor: "#eef2e9",
            borderWidth: 1,
          },
        },
      },
    ],
  };
}

interface TreeMapPanelProps {
  repoId: number;
}

export function TreeMapPanel({ repoId }: TreeMapPanelProps) {
  const { data, loading, error, refresh } = useRequest(() => api.tree(repoId), [repoId]);
  const [weighting, setWeighting] = useState<Weighting>("size");

  const option = useMemo(
    () => (data ? treemapOption(data.nodes ?? [], weighting) : null),
    [data, weighting],
  );

  const hasNodes = Boolean(data && (data.nodes ?? []).length > 0);

  return (
    <section className="panel treemap-panel">
      <div className="treemap-head">
        <div>
          <h2>目录体积</h2>
          <p>
            {weighting === "size" ? "按字节统计" : "按文件数统计"} · 悬停查看路径与明细
          </p>
        </div>
        {hasNodes && (
          <div className="treemap-toggle" role="group" aria-label="目录统计口径">
            {WEIGHTINGS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={weighting === item.value ? "active" : undefined}
                aria-pressed={weighting === item.value}
                onClick={() => setWeighting(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {hasNodes && data && (
        <div className="treemap-summary">
          <span>
            总大小 <strong>{formatBytes(data.total_size)}</strong>
          </span>
          <span>
            文件 <strong>{formatNumber(data.total_files)}</strong>
          </span>
          <span className="mono" title={data.commit_sha ?? undefined}>
            {shortSha(data.commit_sha)}
          </span>
          {data.truncated && (
            <span className="treemap-note">目录过大，仅展示部分条目</span>
          )}
        </div>
      )}

      {loading ? (
        <div className="treemap-state">
          <Spinner label="正在加载目录树" />
          <span>正在构建目录树…</span>
        </div>
      ) : error ? (
        <EmptyState
          title="目录树加载失败"
          description={error}
          icon={<FileIcon size={28} />}
          action={
            <button type="button" className="button secondary compact" onClick={refresh}>
              重试
            </button>
          }
        />
      ) : !hasNodes ? (
        <EmptyState
          title="暂无目录树"
          description="同步完成并生成文件清单后，这里会按目录展示体积分布。"
          icon={<FileIcon size={28} />}
        />
      ) : option ? (
        <div className="treemap-chart">
          <EChart option={option} height={460} ariaLabel="仓库目录体积矩形树图" />
        </div>
      ) : null}
    </section>
  );
}
