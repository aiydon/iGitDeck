import type { EChartsOption } from "echarts";

import type { LanguageSlice, TrendPoint } from "../api/client";
import { compactNumber, formatChartDate, formatNumber } from "./format";
import { languageColor } from "./languageColor";

export interface LanguageDatum {
  name: string;
  value: number;
  percent: number;
  repos: number;
  color: string;
  other: boolean;
}

const OTHER_COLOR = "#98a096";
const MAX_SEGMENTS = 7;

const TOOLTIP_STYLE = {
  backgroundColor: "#18201a",
  borderColor: "rgba(255,255,255,0.14)",
  borderWidth: 1,
  textStyle: { color: "#eef2e9", fontSize: 12 },
} as const;

/** Keep the biggest languages, folding the tail into one "其他" slice. */
export function toLanguageData(languages: LanguageSlice[]): LanguageDatum[] {
  const shown = languages.slice(0, MAX_SEGMENTS).map((language) => ({
    name: language.name,
    value: language.code_lines,
    percent: language.percent,
    repos: language.repos,
    color: languageColor(language.name),
    other: false,
  }));
  const rest = languages.slice(MAX_SEGMENTS);
  if (rest.length > 0) {
    shown.push({
      name: "其他",
      value: rest.reduce((sum, language) => sum + language.code_lines, 0),
      percent: rest.reduce((sum, language) => sum + language.percent, 0),
      repos: 0,
      color: OTHER_COLOR,
      other: true,
    });
  }
  return shown;
}

export function languageDonutOption(data: LanguageDatum[]): EChartsOption {
  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      ...TOOLTIP_STYLE,
      valueFormatter: (value) => `${formatNumber(Number(value))} 行`,
    },
    series: [
      {
        type: "pie",
        radius: ["64%", "84%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderColor: "transparent", borderWidth: 2 },
        emphasis: { scale: true, scaleSize: 5 },
        data: data.map((item) => ({
          name: item.name,
          value: item.value,
          itemStyle: { color: item.color },
        })),
      },
    ],
  };
}

export function trendChartOption(points: TrendPoint[]): EChartsOption {
  return {
    backgroundColor: "transparent",
    grid: { left: 52, right: 24, top: 24, bottom: 42 },
    tooltip: {
      trigger: "axis",
      ...TOOLTIP_STYLE,
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: points.map((point) => formatChartDate(point.captured_at)),
      axisLine: { lineStyle: { color: "rgba(128,136,124,0.24)" } },
      axisTick: { show: false },
      axisLabel: { color: "#8b9288", fontSize: 11, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#8b9288",
        fontSize: 11,
        formatter: (value: number | string) => compactNumber(Number(value)),
      },
      splitLine: { lineStyle: { color: "rgba(128,136,124,0.16)" } },
    },
    series: [
      {
        name: "代码行",
        type: "line",
        data: points.map((point) => point.code_lines),
        smooth: false,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { color: "#4f9a6f", width: 2 },
        itemStyle: { color: "#4f9a6f" },
        areaStyle: { color: "rgba(79,154,111,0.12)" },
      },
    ],
  };
}
