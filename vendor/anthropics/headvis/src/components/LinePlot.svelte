<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  let {
    values = [],
    edges = [],
    xFormat = 'integer',
  } = $props()

  const margin = { top: 10, right: 15, bottom: 28, left: 50 }
  const viewW = 500
  const viewH = 180
  const plotW = viewW - margin.left - margin.right
  const plotH = viewH - margin.top - margin.bottom

  let maxValue = $derived(values.length ? Math.max(...values) : 1)
  let xExtent = $derived([
    edges[0] ?? 0,
    edges[Math.min(values.length - 1, edges.length - 1)] ?? 1,
  ])

  function x(val) {
    const range = xExtent[1] - xExtent[0] || 1
    return margin.left + ((val - xExtent[0]) / range) * plotW
  }
  function y(val) {
    return margin.top + plotH * (1 - val / maxValue)
  }

  let points = $derived(
    values.map((v, i) => `${x(edges[i])},${y(v)}`).join(' ')
  )

  function xTicks(n = 5) {
    const [lo, hi] = xExtent
    if (xFormat === 'integer') {
      // Pick a nice step size (multiples of 1, 2, 5, 10, 20, 50, ...)
      const rawStep = (hi - lo) / n
      const mag = Math.pow(10, Math.floor(Math.log10(rawStep)))
      const residual = rawStep / mag
      const niceStep = residual <= 1.5 ? mag : residual <= 3.5 ? 2 * mag : residual <= 7.5 ? 5 * mag : 10 * mag
      const start = Math.ceil(lo / niceStep) * niceStep
      const ticks = []
      for (let t = start; t <= hi; t += niceStep) {
        ticks.push(t)
      }
      return ticks
    }
    return Array.from({ length: n + 1 }, (_, i) => lo + (hi - lo) * i / n)
  }
  function yTicks(n = 4) {
    return Array.from({ length: n + 1 }, (_, i) => (maxValue * i) / n)
  }

  function fmtX(v) {
    if (xFormat === 'integer') return Math.round(v).toString()
    if (v >= 1) return v.toFixed(1)
    return v.toFixed(3)
  }
  function fmtY(v) {
    if (v === 0) return '0'
    if (v >= 0.01) return v.toFixed(2)
    return v.toExponential(1)
  }

  // Hover state
  let hoverIdx = $state(null)
  let svgEl = $state(null)

  function handleMouseMove(event) {
    if (!svgEl || values.length === 0) return
    const rect = svgEl.getBoundingClientRect()
    // Convert mouse position to SVG viewBox coordinates
    const mouseX = ((event.clientX - rect.left) / rect.width) * viewW
    // Find nearest data point by x distance
    let bestIdx = 0
    let bestDist = Infinity
    for (let i = 0; i < values.length; i++) {
      const px = x(edges[i])
      const dist = Math.abs(mouseX - px)
      if (dist < bestDist) {
        bestDist = dist
        bestIdx = i
      }
    }
    hoverIdx = bestIdx
  }

  function handleMouseLeave() {
    hoverIdx = null
  }
</script>

<svg viewBox="0 0 {viewW} {viewH}" preserveAspectRatio="xMidYMid meet"
     bind:this={svgEl}
     onmousemove={handleMouseMove}
     onmouseleave={handleMouseLeave}
>
  <!-- grid lines -->
  {#each yTicks() as t}
    <line x1={margin.left} y1={y(t)} x2={viewW - margin.right} y2={y(t)}
          stroke="#eee" stroke-width="0.5" />
  {/each}
  <!-- axes -->
  <line x1={margin.left} y1={margin.top} x2={margin.left} y2={margin.top + plotH}
        stroke="#ccc" stroke-width="0.5" />
  <line x1={margin.left} y1={margin.top + plotH} x2={viewW - margin.right} y2={margin.top + plotH}
        stroke="#ccc" stroke-width="0.5" />
  <!-- y labels -->
  {#each yTicks() as t}
    <text x={margin.left - 4} y={y(t)} text-anchor="end" dominant-baseline="middle"
          font-size="9" fill="#888" font-family="monospace">{fmtY(t)}</text>
  {/each}
  <!-- x labels -->
  {#each xTicks() as t}
    <text x={x(t)} y={viewH - 4} text-anchor="middle"
          font-size="9" fill="#888" font-family="monospace">{fmtX(t)}</text>
  {/each}
  <!-- line -->
  <polyline fill="none" stroke="#4285f4" stroke-width="1.5" points={points} />
  <!-- hover elements -->
  {#if hoverIdx != null}
    {@const hx = x(edges[hoverIdx])}
    {@const hy = y(values[hoverIdx])}
    <!-- vertical crosshair -->
    <line x1={hx} y1={margin.top} x2={hx} y2={margin.top + plotH}
          stroke="#4285f4" stroke-width="0.5" stroke-dasharray="3,2" opacity="0.5" />
    <!-- dot -->
    <circle cx={hx} cy={hy} r="3.5" fill="#4285f4" stroke="white" stroke-width="1.5" />
    <!-- tooltip background -->
    {@const label = `${fmtX(edges[hoverIdx])}: ${fmtY(values[hoverIdx])}`}
    {@const tooltipW = label.length * 5.5 + 10}
    {@const tooltipH = 16}
    {@const flipX = hx + tooltipW + 6 > viewW - margin.right}
    {@const tx = flipX ? hx - tooltipW - 6 : hx + 6}
    {@const flipY = hy - tooltipH - 6 < margin.top}
    {@const ty = flipY ? hy + 6 : hy - tooltipH - 6}
    <rect x={tx} y={ty} width={tooltipW} height={tooltipH}
          rx="3" fill="rgba(0,0,0,0.8)" />
    <text x={tx + tooltipW / 2} y={ty + tooltipH / 2 + 1}
          text-anchor="middle" dominant-baseline="middle"
          font-size="9" fill="white" font-family="monospace">{label}</text>
  {/if}
  <!-- invisible overlay to capture mouse events over the full plot area -->
  <rect x={margin.left} y={margin.top} width={plotW} height={plotH}
        fill="transparent" style="cursor: crosshair;" />
</svg>

<style>
  svg {
    width: 100%;
    max-width: 500px;
    height: auto;
    display: block;
  }
</style>
