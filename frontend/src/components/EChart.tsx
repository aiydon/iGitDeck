import { LineChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";
import { useEffect, useRef } from "react";

echarts.use([LineChart, PieChart, GridComponent, TooltipComponent, CanvasRenderer]);

interface EChartProps {
  option: EChartsOption;
  height?: number;
  ariaLabel?: string;
}

export function EChart({ option, height = 280, ariaLabel }: EChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = echarts.init(container, undefined, { renderer: "canvas" });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true });
  }, [option]);

  return (
    <div
      ref={containerRef}
      className="echart"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
    />
  );
}
