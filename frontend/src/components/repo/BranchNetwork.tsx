import { useLayoutEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";

import { api } from "../../api/client";
import type { NetworkBranch, NetworkCommit } from "../../api/client";
import { errorMessage, relativeTime, shortSha } from "../../lib/format";
import { useRequest } from "../../lib/hooks";
import { EmptyState } from "../EmptyState";
import { BranchIcon } from "../icons";
import { Spinner } from "../Spinner";

const MAX_BRANCHES = 12;
const MIN_WIDTH = 720;
const MIN_HEIGHT = 520;
const MAX_HEIGHT = 720;
const HEADER_HEIGHT = 128;
const PLOT_TOP_GAP = 14;
const BOTTOM_PADDING = 30;
const LEFT_PADDING = 26;
const RIGHT_AXIS = 74;
const MAX_COLUMN_WIDTH = 120;
const DOT_RADIUS = 3.7;
const DEFAULT_DOT_RADIUS = 4;
const HIT_RADIUS = 9;
const LABEL_FONT_WIDTH = 6.4;
const LABEL_MAX_WIDTH = 118;

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
  isDefault: boolean;
}

interface NetworkLane {
  branch: NetworkBranch;
  isDefault: boolean;
  x: number;
}

interface NetworkEdge {
  key: string;
  from: PlacedCommit;
  to: PlacedCommit;
}

interface NetworkTick {
  key: string;
  y: number;
  label: string;
}

interface NetworkGraph {
  lanes: NetworkLane[];
  commits: PlacedCommit[];
  edges: NetworkEdge[];
  ticks: NetworkTick[];
  width: number;
  height: number;
  plotTop: number;
  plotBottom: number;
  plotRight: number;
}

interface HoverState {
  key: string;
  commit: NetworkCommit;
  anchorX: number;
  anchorY: number;
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

function textWidth(text: string): number {
  let width = 0;
  for (const char of text) {
    width += /[\u2e80-\u9fff\uac00-\ud7af]/.test(char) ? 11 : LABEL_FONT_WIDTH;
  }
  return width;
}

function truncateName(name: string, maxWidth: number): string {
  if (textWidth(name) <= maxWidth) return name;
  const chars = Array.from(name);
  while (chars.length > 0 && textWidth(`${chars.join("")}…`) > maxWidth) chars.pop();
  return `${chars.join("")}…`;
}

function formatTick(time: number, span: number): string {
  const date = new Date(time);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  if (span > 1000 * 60 * 60 * 24 * 180) return `${date.getFullYear()}-${month}`;
  if (span < 1000 * 60 * 60 * 24 * 2) {
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${month}-${day} ${hours}:${minutes}`;
  }
  return `${month}-${day}`;
}

function buildGraph(
  branches: NetworkBranch[],
  defaultBranch: string | null,
  width: number,
): NetworkGraph {
  const placed: PlacedCommit[] = [];
  branches.forEach((branch, branchIndex) => {
    const isDefault = isDefaultBranch(branch, defaultBranch);
    (branch.commits ?? []).forEach((commit) => {
      const time = Date.parse(commit.committed_at);
      if (Number.isNaN(time)) return;
      placed.push({ commit, branchIndex, time, x: 0, y: 0, isDefault });
    });
  });

  // Time drives the vertical scale, so height only grows slightly with volume.
  const height = Math.min(MAX_HEIGHT, MIN_HEIGHT + placed.length * 1.2);
  const plotTop = HEADER_HEIGHT + PLOT_TOP_GAP;
  const plotBottom = height - BOTTOM_PADDING;
  const plotHeight = Math.max(40, plotBottom - plotTop);
  const plotWidth = Math.max(1, width - LEFT_PADDING - RIGHT_AXIS);
  const columnCount = Math.max(1, branches.length);
  const columnWidth = Math.min(MAX_COLUMN_WIDTH, plotWidth / columnCount);
  const blockWidth = columnWidth * columnCount;
  const blockStart = LEFT_PADDING + Math.max(0, (plotWidth - blockWidth) / 2);
  const laneX = (index: number) => blockStart + columnWidth * (index + 0.5);

  let domainStart = 0;
  let domainEnd = 1;
  let newest = 0;
  let oldest = 0;
  let span = 0;

  if (placed.length > 0) {
    newest = Math.max(...placed.map((entry) => entry.time));
    oldest = Math.min(...placed.map((entry) => entry.time));
    span = newest - oldest;
    const padding = span > 0 ? span * 0.04 : 30 * 60 * 1000;
    domainStart = oldest - padding;
    domainEnd = newest + padding;
  }

  const yFor = (time: number) =>
    plotTop + ((domainEnd - time) / (domainEnd - domainStart)) * plotHeight;

  placed.forEach((entry) => {
    entry.x = laneX(entry.branchIndex);
    entry.y = plotTop + ((domainEnd - entry.time) / (domainEnd - domainStart)) * plotHeight;
  });

  const lanes: NetworkLane[] = branches.map((branch, index) => ({
    branch,
    isDefault: isDefaultBranch(branch, defaultBranch),
    x: laneX(index),
  }));

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
      const key = `${entry.commit.sha}->${parentSha}@${entry.branchIndex}:${target.branchIndex}`;
      if (seen.has(key)) return;
      seen.add(key);
      edges.push({ key, from: entry, to: target });
    });
  });

  const ticks: NetworkTick[] = [];
  const tickTimes = new Set<number>();
  for (let index = 0; index < 4; index += 1) {
    const time = newest - (span * index) / 3;
    if (tickTimes.has(time)) continue;
    tickTimes.add(time);
    ticks.push({ key: `tick-${time}`, y: yFor(time), label: formatTick(time, span) });
  }

  return {
    lanes,
    commits: placed,
    edges,
    ticks,
    width,
    height,
    plotTop,
    plotBottom,
    plotRight: LEFT_PADDING + plotWidth,
  };
}

export function BranchNetwork({ repoId, defaultBranch }: BranchNetworkProps) {
  const { data, loading, error } = useRequest(() => api.network(repoId), [repoId]);
  const [hovered, setHovered] = useState<HoverState | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ left: number; top: number } | null>(null);
  const [availableWidth, setAvailableWidth] = useState(MIN_WIDTH);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const measure = () =>
      setAvailableWidth(Math.max(MIN_WIDTH, Math.floor(scroller.clientWidth)));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(scroller);
    return () => observer.disconnect();
  }, [data]);

  // Keep the tooltip inside the panel: clamp horizontally, flip vertically.
  useLayoutEffect(() => {
    if (!hovered) {
      setTooltipPos(null);
      return;
    }
    const tooltip = tooltipRef.current;
    const panel = panelRef.current;
    if (!tooltip || !panel) return;
    const margin = 8;
    const rect = panel.getBoundingClientRect();
    const tooltipWidth = tooltip.offsetWidth;
    const tooltipHeight = tooltip.offsetHeight;
    let left = hovered.anchorX - tooltipWidth / 2;
    left = Math.min(Math.max(left, margin), Math.max(margin, rect.width - tooltipWidth - margin));
    let top = hovered.anchorY - tooltipHeight - 10;
    if (top < margin) top = hovered.anchorY + 18;
    top = Math.min(Math.max(top, margin), Math.max(margin, rect.height - tooltipHeight - margin));
    setTooltipPos({ left, top });
  }, [hovered]);

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

  const visibleBranches = useMemo(() => branches.slice(0, MAX_BRANCHES), [branches]);
  const hiddenBranches = branches.length - visibleBranches.length;
  const graph = useMemo(
    () => buildGraph(visibleBranches, defaultBranch, availableWidth),
    [visibleBranches, defaultBranch, availableWidth],
  );

  function showTooltip(
    event: MouseEvent<SVGCircleElement>,
    entry: PlacedCommit,
    key: string,
  ) {
    const panel = panelRef.current;
    if (!panel) return;
    const panelRect = panel.getBoundingClientRect();
    const hitRect = event.currentTarget.getBoundingClientRect();
    setHovered({
      key,
      commit: entry.commit,
      anchorX: hitRect.left - panelRect.left + hitRect.width / 2,
      anchorY: hitRect.top - panelRect.top,
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
  const columnTop = graph.plotTop;
  const columnBottom = graph.plotBottom;

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

      <div className="network-scroll" ref={scrollRef}>
        <div className="network-canvas" style={{ width: `${graph.width}px` }}>
          <svg
            className="network-svg"
            viewBox={`0 0 ${graph.width} ${graph.height}`}
            height={graph.height}
            role="img"
            aria-label="分支提交网络图：横轴为分支，纵轴为提交时间"
          >
            <g className="network-time-axis" aria-hidden="true">
              {graph.ticks.map((tick) => (
                <g key={tick.key}>
                  <line
                    className="network-time-grid"
                    x1={LEFT_PADDING}
                    y1={tick.y}
                    x2={graph.plotRight}
                    y2={tick.y}
                  />
                  <line
                    className="network-axis-tick"
                    x1={graph.plotRight}
                    y1={tick.y}
                    x2={graph.plotRight + 5}
                    y2={tick.y}
                  />
                  <text className="network-axis-label" x={graph.plotRight + 9} y={tick.y + 3.2}>
                    {tick.label}
                  </text>
                </g>
              ))}
            </g>

            {graph.edges.map((edge) => {
              const midY = (edge.from.y + edge.to.y) / 2;
              return (
                <path
                  key={edge.key}
                  className="network-edge"
                  d={`M ${edge.from.x} ${edge.from.y} C ${edge.from.x} ${midY}, ${edge.to.x} ${midY}, ${edge.to.x} ${edge.to.y}`}
                />
              );
            })}

            {graph.lanes.map((lane) => (
              <line
                key={`lane-${lane.branch.name}`}
                className={`network-lane${lane.isDefault ? " is-default" : ""}`}
                x1={lane.x}
                y1={columnTop}
                x2={lane.x}
                y2={columnBottom}
              />
            ))}

            {graph.commits.map((entry) => {
              const key = `${entry.branchIndex}-${entry.commit.sha}`;
              const isHovered = hovered?.key === key;
              return (
                <g key={key}>
                  <circle
                    className={`network-dot${entry.isDefault ? " is-default" : ""}${isHovered ? " is-hovered" : ""}`}
                    cx={entry.x}
                    cy={entry.y}
                    r={
                      isHovered
                        ? DOT_RADIUS + 1.2
                        : entry.isDefault
                          ? DEFAULT_DOT_RADIUS
                          : DOT_RADIUS
                    }
                  />
                  <circle
                    className="network-dot-hit"
                    cx={entry.x}
                    cy={entry.y}
                    r={HIT_RADIUS}
                    onMouseEnter={(event) => showTooltip(event, entry, key)}
                    onMouseLeave={() => setHovered(null)}
                  />
                </g>
              );
            })}

            {graph.lanes.map((lane) => {
              const label = truncateName(lane.branch.name, LABEL_MAX_WIDTH);
              const chipX = textWidth(label) + 7;
              return (
                <g
                  key={`head-${lane.branch.name}`}
                  className="network-column"
                  transform={`translate(${lane.x} ${HEADER_HEIGHT - 6}) rotate(-50)`}
                >
                  <title>{lane.branch.name}</title>
                  <text
                    className={`network-column-label${lane.isDefault ? " is-default" : ""}`}
                    textAnchor="start"
                  >
                    {label}
                  </text>
                  {lane.isDefault && (
                    <g className="network-default-chip">
                      <rect x={chipX} y={-9.5} width={25} height={12} rx={6} />
                      <text x={chipX + 12.5} y={-0.5} textAnchor="middle">
                        默认
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {hovered && (
        <div
          ref={tooltipRef}
          className="network-tooltip"
          role="tooltip"
          style={{
            left: `${tooltipPos?.left ?? hovered.anchorX}px`,
            top: `${tooltipPos?.top ?? hovered.anchorY}px`,
            visibility: tooltipPos ? "visible" : "hidden",
          }}
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
