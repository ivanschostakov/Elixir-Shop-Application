import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react"

export type MetricLineChartPoint = {
  key: string
  label: string
  tooltipLabel?: string
  values: Record<string, number | null | undefined>
}

export type MetricLineChartSeries = {
  key: string
  label: string
  color: string
  axis?: "left" | "right"
  formatValue?: (value: number) => string
}

type MetricLineChartProps = {
  data: MetricLineChartPoint[]
  series: MetricLineChartSeries[]
  description: string
  ariaLabel: string
  emptyText: string
  height?: number
  leftAxisFormatter?: (value: number) => string
  rightAxisFormatter?: (value: number) => string
}

const DEFAULT_WIDTH = 960
const DEFAULT_HEIGHT = 260
const TOP = 18
const BOTTOM = 38
const LEFT = 58

function finiteValue(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, value) : null
}

function niceMaximum(value: number) {
  if (value <= 0) return 1
  const exponent = Math.floor(Math.log10(value))
  const magnitude = 10 ** exponent
  const normalized = value / magnitude
  const nice = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return nice * magnitude
}

function axisMaximum(data: MetricLineChartPoint[], series: MetricLineChartSeries[], axis: "left" | "right") {
  const keys = series.filter((item) => (item.axis || "left") === axis).map((item) => item.key)
  const maximum = Math.max(0, ...data.flatMap((point) => keys.map((key) => finiteValue(point.values[key]) || 0)))
  return niceMaximum(maximum)
}

function defaultAxisValue(value: number) {
  return new Intl.NumberFormat(undefined, { notation: value >= 10_000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value)
}

function linePath(
  data: MetricLineChartPoint[],
  key: string,
  maximum: number,
  plotWidth: number,
  plotHeight: number,
) {
  return data.reduce((path, point, index) => {
    const value = finiteValue(point.values[key])
    if (value === null) return path
    const x = LEFT + (data.length === 1 ? plotWidth / 2 : index / (data.length - 1) * plotWidth)
    const y = TOP + plotHeight - value / maximum * plotHeight
    return `${path}${path ? " L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`
  }, "")
}

export function MetricLineChart({
  data,
  series,
  description,
  ariaLabel,
  emptyText,
  height = DEFAULT_HEIGHT,
  leftAxisFormatter = defaultAxisValue,
  rightAxisFormatter = defaultAxisValue,
}: MetricLineChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [chartWidth, setChartWidth] = useState(DEFAULT_WIDTH)
  const canvasRef = useRef<HTMLDivElement>(null)
  const rightSeries = series.filter((item) => item.axis === "right")
  const rightMargin = rightSeries.length ? 58 : 18
  const plotWidth = Math.max(120, chartWidth - LEFT - rightMargin)
  const plotHeight = height - TOP - BOTTOM
  const leftMaximum = useMemo(() => axisMaximum(data, series, "left"), [data, series])
  const rightMaximum = useMemo(() => axisMaximum(data, series, "right"), [data, series])
  const xLabelIndexes = useMemo(() => {
    const maximumLabels = chartWidth < 520 ? 4 : 7
    if (data.length <= maximumLabels) return new Set(data.map((_, index) => index))
    const indexes = new Set<number>()
    for (let step = 0; step < maximumLabels; step += 1) indexes.add(Math.round(step * (data.length - 1) / (maximumLabels - 1)))
    return indexes
  }, [chartWidth, data])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const updateWidth = () => setChartWidth(Math.max(280, Math.round(canvas.getBoundingClientRect().width)))
    updateWidth()
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", updateWidth)
      return () => window.removeEventListener("resize", updateWidth)
    }
    const observer = new ResizeObserver(updateWidth)
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [data.length])

  if (!data.length || !series.length) return <div className="metric-line-chart-empty">{emptyText}</div>

  const activePoint = activeIndex === null ? null : data[activeIndex]
  const activeX = activeIndex === null
    ? null
    : LEFT + (data.length === 1 ? plotWidth / 2 : activeIndex / (data.length - 1) * plotWidth)
  const tooltipAlignment = activeIndex !== null && activeIndex <= Math.max(1, data.length * 0.2)
    ? "start"
    : activeIndex !== null && activeIndex >= data.length * 0.8
      ? "end"
      : "center"

  const updateActivePoint = (event: ReactPointerEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect()
    const viewX = (event.clientX - bounds.left) / Math.max(bounds.width, 1) * chartWidth
    const ratio = Math.min(1, Math.max(0, (viewX - LEFT) / Math.max(plotWidth, 1)))
    setActiveIndex(Math.round(ratio * Math.max(data.length - 1, 0)))
  }

  return (
    <div
      className="metric-line-chart"
      tabIndex={0}
      role="figure"
      aria-label={ariaLabel}
      onBlur={() => setActiveIndex(null)}
      onKeyDown={(event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return
        event.preventDefault()
        setActiveIndex((current) => {
          if (current === null) return event.key === "ArrowRight" ? 0 : data.length - 1
          return Math.min(data.length - 1, Math.max(0, current + (event.key === "ArrowRight" ? 1 : -1)))
        })
      }}
    >
      <div className="metric-line-chart-legend" aria-hidden="true">
        {series.map((item) => <span key={item.key}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}
      </div>
      <div className="metric-line-chart-canvas" ref={canvasRef}>
        <svg
          viewBox={`0 0 ${chartWidth} ${height}`}
          preserveAspectRatio="none"
          style={{ height }}
          onPointerMove={updateActivePoint}
          onPointerLeave={() => setActiveIndex(null)}
          aria-hidden="true"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const y = TOP + plotHeight * ratio
            const leftValue = leftMaximum * (1 - ratio)
            const rightValue = rightMaximum * (1 - ratio)
            return <g key={ratio}>
              <line className="metric-line-chart-grid" x1={LEFT} x2={LEFT + plotWidth} y1={y} y2={y} />
              <text className="metric-line-chart-axis" x={LEFT - 10} y={y + 4} textAnchor="end">{leftAxisFormatter(leftValue)}</text>
              {rightSeries.length ? <text className="metric-line-chart-axis" x={LEFT + plotWidth + 10} y={y + 4}>{rightAxisFormatter(rightValue)}</text> : null}
            </g>
          })}
          {data.map((point, index) => {
            if (!xLabelIndexes.has(index)) return null
            const x = LEFT + (data.length === 1 ? plotWidth / 2 : index / (data.length - 1) * plotWidth)
            return <text key={point.key} className="metric-line-chart-axis metric-line-chart-x-axis" x={x} y={height - 10} textAnchor="middle">{point.label}</text>
          })}
          {series.map((item) => {
            const maximum = item.axis === "right" ? rightMaximum : leftMaximum
            const onlyValue = data.length === 1 ? finiteValue(data[0].values[item.key]) : null
            return <g key={item.key}>
              <path
                className="metric-line-chart-path"
                d={linePath(data, item.key, maximum, plotWidth, plotHeight)}
                stroke={item.color}
              />
              {onlyValue !== null ? <circle className="metric-line-chart-single-point" cx={LEFT + plotWidth / 2} cy={TOP + plotHeight - onlyValue / maximum * plotHeight} r={5} fill={item.color} /> : null}
            </g>
          })}
          {activeX !== null && activePoint ? <>
            <line className="metric-line-chart-cursor" x1={activeX} x2={activeX} y1={TOP} y2={TOP + plotHeight} />
            {series.map((item) => {
              const value = finiteValue(activePoint.values[item.key])
              if (value === null) return null
              const maximum = item.axis === "right" ? rightMaximum : leftMaximum
              const y = TOP + plotHeight - value / maximum * plotHeight
              return <circle key={item.key} className="metric-line-chart-point" cx={activeX} cy={y} r={5} fill={item.color} />
            })}
          </> : null}
        </svg>
        {activePoint && activeX !== null ? <div
          className={`metric-line-chart-tooltip metric-line-chart-tooltip-${tooltipAlignment}`}
          style={{ left: `${activeX / chartWidth * 100}%` }}
        >
          <strong>{activePoint.tooltipLabel || activePoint.label}</strong>
          {series.map((item) => {
            const value = finiteValue(activePoint.values[item.key])
            return <div key={item.key}><span><i style={{ backgroundColor: item.color }} />{item.label}</span><b>{value === null ? "—" : (item.formatValue || defaultAxisValue)(value)}</b></div>
          })}
        </div> : null}
      </div>
      <p className="metric-line-chart-description">{description}</p>
    </div>
  )
}
