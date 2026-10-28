import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";

import { api } from "../../api/client";
import type { NetworkBranch, NetworkCommit } from "../../api/client";
import { errorMessage, relativeTime, shortSha } from "../../lib/format";
import { useRequest } from "../../lib/hooks";
import { EmptyState } from "../EmptyState";
import { BranchIcon } from "../icons";
import { Spinner } from "../Spinner";

const MAX_ROWS = 12;
const ROW_HEIGHT = 28;
const TOP_PADDING = 12;
const BOTTOM_PADDING = 10;
const SVG_WIDTH = 760;
const MIN_SVG_WIDTH = 640;
const X_PADDING = 14;

interface BranchNetworkProps {
  repoId: number;
  defaultBranch: string | null;
}

interface PlacedCommit {
  commit: NetworkCommit;
  branchIndex: number;
  time: number;
  x: number;
  y: number;
}

interface NetworkRow {
  branch: NetworkBranch;
  isDefault: boolean;
  y: number;
  line: { x1: number; x2: number } | null;
}

interface NetworkEdge {
  key: string;
  from: PlacedCommit;
  to: PlacedCommit;
}

interface NetworkGraph {
  rows: NetworkRow[];
  commits: PlacedCommit[];
  edges: NetworkEdge[];
  height: number;
}

interface HoverState {
  commit: NetworkCommit;
  left: number;
  top: number;
  below: boolean;
}

function latestTime(branch: NetworkBranch): number {
  return (branch.commits ?? []).reduce((latest, commit) => {
    const time = Date.parse(commit.committed_at);
    return Number.isNaN(time) || time <= latest ? latest : time;
  }, Number.NEGATIVE_INFINITY);
}

function isDefaultBranch(branch: NetworkBranch, defaultBranch: string | null): boolean {
  return branch.is_default || (defaultBranch !== null && branch.name === defaultBranch);
}

function buildGraph(
  branches: NetworkBranch[],
  defaultBranch: string | null,
  width: number,
): NetworkGraph {
  const height = TOP_PADDING + branches.length * ROW_HEIGHT + BOTTOM_PADDING;
  const rowY = (index: number) => TOP_PADDING + index * ROW_HEIGHT + ROW_HEIGHT / 2;

  const placed: PlacedCommit[] = [];
  branches.forEach((branch, branchIndex) => {
    (branch.commits ?? []).forEach((commit) => {
      const time = Date.parse(commit.committed_at);
      if (Number.isNaN(time)) return;
      placed.push({ commit, branchIndex, time, x: 0, y: rowY(branchIndex) });
    });
  });

  if (placed.length > 0) {
    const oldest = Math.min(...placed.map((entry) => entry.time));
    const newest = Math.max(...placed.map((entry) => entry.time));
    const span = newest - oldest;
    // Pad the time range by 4% on each side so edge dots never clip.
    const padding = span > 0 ? span * 0.04 : 1000;
    const domainStart = oldest - padding;
    const domainEnd = newest + padding;
    const usable = width - X_PADDING * 2;
    placed.forEach((entry) => {
      entry.x = X_PADDING + ((entry.time - domainStart) / (domainEnd - domainStart)) * usable;
    });
  }

  const rows: NetworkRow[] = branches.map((branch, index) => {
    const own = placed.filter((entry) => entry.branchIndex === index);
    const line =
      own.length > 0
        ? {
            x1: Math.min(...own.map((entry) => entry.x)),
            x2: Math.max(...own.map((entry) => entry.x)),
          }
        : null;
    return { branch, isDefault: isDefaultBranch(branch, defaultBranch), y: rowY(index), line };
  });

  const bySha = new Map<string, PlacedCommit[]>();
  placed.forEach((entry) => {
    const list = bySha.get(entry.commit.sha) ?? [];
    list.push(entry);
    bySha.set(entry.commit.sha, list);
  });

  const edges: NetworkEdge[] = [];
  const seen = new Set<string>();
  placed.forEach((entry) => {
    (entry.commit.parents ?? []).forEach((parentSha) => {
      const target = (bySha.get(parentSha) ?? []).find(
        (candidate) => candidate.branchIndex !== entry.branchIndex,
      );
      if (!target) return;
      const key = `${entry.commit.sha}->${target.commit.sha}@${entry.branchIndex}:${target.branchIndex}`;
      if (seen.has(key)) return;
      seen.add(key);
      edges.push({ key, from: entry, to: target });
    });
  });

  return { rows, commits: placed, edges, height };
}

export function BranchNetwork({ repoId, defaultBranch }: BranchNetworkProps) {
  const { data, loading, error } = useRequest(() => api.network(repoId), [repoId]);
  const [hovered, setHovered] = useState<HoverState | null>(null);
  const [svgWidth, setSvgWidth] = useState(SVG_WIDTH);
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);

  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const measure = () =>
      setSvgWidth(Math.max(MIN_SVG_WIDTH, Math.round(canvas.clientWidth)));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [data]);

  const branches = useMemo(() => {
    const list = [...(data?.branches ?? [])];
    list.sort((left, right) => {
      const leftDefault = isDefaultBranch(left, defaultBranch);
      const rightDefault = isDefaultBranch(right, defaultBranch);
      if (leftDefault !== rightDefault) return leftDefault ? -1 : 1;
      return latestTime(right) - latestTime(left);
    });
    return list;
  }, [data, defaultBranch]);

  const visibleBranches = branches.slice(0, MAX_ROWS);
  const hiddenBranches = branches.length - visibleBranches.length;
  const graph = useMemo(
    () => buildGraph(visibleBranches, defaultBranch, svgWidth),
    [visibleBranches, defaultBranch, svgWidth],
  );

  function showTooltip(event: MouseEvent<SVGCircleElement>, commit: NetworkCommit) {
    const panel = panelRef.current;
    if (!panel) return;
    const dot = event.currentTarget.getBoundingClientRect();
    const rect = panel.getBoundingClientRect();
    const half = Math.min(120, rect.width / 2);
    const center = dot.left - rect.left + dot.width / 2;
    const top = dot.top - rect.top;
    setHovered({
      commit,
      left: Math.min(Math.max(center, half), rect.width - half),
      top,
      // Top rows cannot open upwards without leaving the panel.
      below: top < 140,
    });
  }

  if (loading && !data) {
    return (
      <section className="panel branch-network">
        <p className="network-loading muted">
          <Spinner label="加载分支网络" />
          加载分支网络…
        </p>
      </section>
    );
  }

  if (!data || branches.length === 0 || graph.commits.length === 0) {
    return (
      <section className="panel branch-network">
        <EmptyState
          title="暂无分支网络数据"
          description={
            error
              ? errorMessage(error)
              : "仓库同步完成后，这里会按时间轴展示分支与它们的提交关系。"
          }
          icon={<BranchIcon size={26} />}
        />
      </section>
    );
  }

  const commitCount = graph.commits.length;

  return (
    <section className="panel branch-network" ref={panelRef}>
      <div className="panel-head network-head">
        <div>
          <h2>分支网络</h2>
          <p>
            {(data.branches ?? []).length} 个分支 · 最近 30 个提交
          </p>
        </div>
        <span className="panel-badge">{commitCount} 个节点</span>
      </div>

      <div className="network-body">
        <div className="network-labels" aria-hidden="true">
          {graph.rows.map((row) => (
            <div
              key={row.branch.name}
              className={`network-row-label${row.isDefault ? " is-default" : ""}`}
              style={{ height: `${ROW_HEIGHT}px` }}
              title={row.branch.name}
            >
              <span>{row.branch.name}</span>
              {row.isDefault && <span className="network-default-chip">默认</span>}
            </div>
          ))}
        </div>

        <div className="network-canvas">
          <div
            className="network-canvas-inner"
            ref={canvasRef}
            style={{ minWidth: `${MIN_SVG_WIDTH}px` }}
          >
            <svg
              className="branch-svg"
              viewBox={`0 0 ${svgWidth} ${graph.height}`}
              height={graph.height}
              role="img"
              aria-label="分支提交网络图"
            >
              {graph.edges.map((edge) => (
                <line
                  key={edge.key}
                  className="network-edge"
                  x1={edge.from.x}
                  y1={edge.from.y}
                  x2={edge.to.x}
                  y2={edge.to.y}
                />
              ))}

              {graph.rows.map((row) => (
                <g key={row.branch.name}>
                  {row.line && (
                    <line
                      className={`network-row-line${row.isDefault ? " is-default" : ""}`}
                      x1={row.line.x1}
                      y1={row.y}
                      x2={row.line.x2}
                      y2={row.y}
                    />
                  )}
                </g>
              ))}

              {graph.commits.map((entry) => (
                <circle
                  key={`${entry.commit.sha}-${entry.branchIndex}`}
                  className={`network-dot${graph.rows[entry.branchIndex].isDefault ? " is-default" : ""}`}
                  cx={entry.x}
                  cy={entry.y}
                  r={hovered?.commit.sha === entry.commit.sha ? 4.5 : 3.2}
                  onMouseEnter={(event) => showTooltip(event, entry.commit)}
                  onMouseLeave={() => setHovered(null)}
                />
              ))}
            </svg>
          </div>
        </div>
      </div>

      {hovered && (
        <div
          className={`network-tooltip${hovered.below ? " below" : ""}`}
          style={{ left: `${hovered.left}px`, top: `${hovered.top}px` }}
          role="tooltip"
        >
          <strong>{hovered.commit.message || "（无提交说明）"}</strong>
          <span className="network-tooltip-meta">
            {hovered.commit.author} · {relativeTime(hovered.commit.committed_at)}
          </span>
          <code>{shortSha(hovered.commit.sha)}</code>
        </div>
      )}

      {(data.truncated || hiddenBranches > 0) && (
        <p className="network-note">
          仓库分支较多，仅显示前 {visibleBranches.length} 个分支的最近提交。
        </p>
      )}
    </section>
  );
}
