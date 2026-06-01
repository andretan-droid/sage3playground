<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import * as Plotly from 'plotly.js-dist-min'
  import { onMount, untrack } from 'svelte'

  let {
    data = [],
    selectedLayer = null,
    selectedHead = null,
    availableMetrics = [],
    scatterConfig = null,  // { default_x, default_y, default_color, discrete_axes }
    dimensionsConfig = null,  // { primary, secondary }
    onSelect = null,
    containerWidth = null,  // Used to trigger resize when parent changes
    aspectRatio = 1.0,  // Width to height ratio for the plot
    colorbarLen = 0.8,  // Fraction of plot width (plotly colorbar.len)
  } = $props()

  // Track whether we've initialized from config
  let initialized = false
  let xAxis = $state('layer')
  let yAxis = $state('head')
  let colorAxis = $state('')

  // Initialize axes from config once when config becomes available
  $effect(() => {
    if (scatterConfig && !initialized) {
      initialized = true
      untrack(() => {
        xAxis = scatterConfig.default_x || 'layer'
        yAxis = scatterConfig.default_y || 'head'
        colorAxis = scatterConfig.default_color || availableMetrics[2] || ''
      })
    }
  })

  let plotDiv = $state(null)
  let mounted = $state(false)

  // Compute height based on container width and aspect ratio
  // Account for padding (32px total from scatter-container padding)
  let computedHeight = $derived(
    containerWidth ? Math.round((containerWidth - 32) / aspectRatio) : 280
  )

  onMount(() => {
    mounted = true
  })

  // Resize plot when container width changes
  $effect(() => {
    if (containerWidth && plotDiv && mounted) {
      // Trigger Plotly resize
      Plotly.Plots.resize(plotDiv)
    }
  })

  // Render scatter plot when data or config changes
  $effect(() => {
    if (!mounted || !plotDiv || !data.length) return

    const xValues = data.map(d => d[xAxis])
    const yValues = data.map(d => d[yAxis])
    const colorValues = data.map(d => d[colorAxis] ?? 0)

    // Find selected point index
    const selectedIdx = data.findIndex(d => d.layer === selectedLayer && d.head === selectedHead)

    // Use orange border for selected point instead of different color
    const lineColors = data.map((d, i) => i === selectedIdx ? '#ff9800' : 'rgba(0,0,0,0)')
    const lineWidths = data.map((d, i) => i === selectedIdx ? 2 : 0)

    // Get config values (declared early to avoid TDZ errors)
    const discreteAxes = scatterConfig?.discrete_axes || ['layer', 'head']
    const primaryDim = dimensionsConfig?.primary || 'layer'
    const secondaryDim = dimensionsConfig?.secondary || 'head'

    const trace = {
      x: xValues,
      y: yValues,
      mode: 'markers',
      type: 'scatter',
      marker: {
        size: 8,
        color: colorValues,
        colorscale: 'Viridis',
        showscale: true,
        line: {
          color: lineColors,
          width: lineWidths,
        },
        colorbar: {
          orientation: 'h',
          y: 1.02,
          yanchor: 'bottom',
          len: colorbarLen,
          x: 0.5,
          thickness: 12,
          tickfont: { size: 10 },
        },
      },
      text: data.map(d => `L${d[primaryDim]}H${d[secondaryDim]}`),
      hovertemplate: '%{text}<br>' + xAxis + ': %{x}<br>' + yAxis + ': %{y}<extra></extra>',
    }

    // Configure x-axis - use discrete ticks if axis is in discreteAxes
    const xaxisConfig = {
      title: '',
      zeroline: false,
      gridcolor: '#e0e0e0',
    }
    if (discreteAxes.includes(xAxis)) {
      const uniqueVals = [...new Set(data.map(d => d[xAxis]))].sort((a, b) => a - b)
      xaxisConfig.tickmode = 'array'
      xaxisConfig.tickvals = uniqueVals
      xaxisConfig.ticktext = uniqueVals.map(v => String(v))
    }

    // Configure y-axis - use discrete ticks if axis is in discreteAxes
    const yaxisConfig = {
      title: '',
      zeroline: false,
      gridcolor: '#e0e0e0',
    }
    if (discreteAxes.includes(yAxis)) {
      const uniqueVals = [...new Set(data.map(d => d[yAxis]))].sort((a, b) => a - b)
      yaxisConfig.tickmode = 'array'
      yaxisConfig.tickvals = uniqueVals
      yaxisConfig.ticktext = uniqueVals.map(v => String(v))
    }

    const layout = {
      xaxis: xaxisConfig,
      yaxis: yaxisConfig,
      margin: { l: 40, r: 10, t: 50, b: 35 },
      hovermode: 'closest',
      plot_bgcolor: '#fafafa',
      paper_bgcolor: '#fafafa',
    }

    const config = {
      responsive: true,
      displayModeBar: false,
    }

    Plotly.react(plotDiv, [trace], layout, config)

    // Handle click events
    plotDiv.on('plotly_click', (eventData) => {
      if (eventData.points.length > 0) {
        const idx = eventData.points[0].pointIndex
        const point = data[idx]
        if (onSelect) {
          onSelect(point.layer, point.head)
        }
      }
    })
  })
</script>

<div class="scatter-wrapper">
  <div bind:this={plotDiv} class="scatter-plot" style="height: {computedHeight}px;"></div>

  <!-- Color axis dropdown (top center) -->
  <div class="axis-dropdown color-axis">
    <select bind:value={colorAxis}>
      <option value="">None</option>
      {#each availableMetrics as metric}
        <option value={metric}>{metric}</option>
      {/each}
    </select>
  </div>

  <!-- X-axis dropdown (bottom center) -->
  <div class="axis-dropdown x-axis">
    <select bind:value={xAxis}>
      {#each availableMetrics as metric}
        <option value={metric}>{metric}</option>
      {/each}
    </select>
  </div>

  <!-- Y-axis dropdown (left side, rotated) -->
  <div class="axis-dropdown y-axis">
    <select bind:value={yAxis}>
      {#each availableMetrics as metric}
        <option value={metric}>{metric}</option>
      {/each}
    </select>
  </div>
</div>

<style>
  .scatter-wrapper {
    position: relative;
    width: 100%;
  }

  .scatter-plot {
    width: 100%;
    background: #fafafa;
  }

  .axis-dropdown {
    position: absolute;
    z-index: 10;
  }

  .axis-dropdown select {
    font-size: 12px;
    padding: 2px 6px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    cursor: pointer;
    font-weight: 600;
    color: #444;
    max-width: 180px;
    text-overflow: ellipsis;
    text-align: center;
    text-align-last: center;
    appearance: none;
    -webkit-appearance: none;
  }

  .axis-dropdown select:hover {
    background: rgba(255, 255, 255, 0.95);
    border-color: #aaa;
    color: #000;
  }

  .axis-dropdown select:focus {
    outline: none;
    background: white;
    border-color: #4285f4;
    color: #000;
  }

  /* X-axis: centered at bottom */
  .x-axis {
    bottom: 4px;
    left: 50%;
    transform: translateX(-50%);
  }

  /* Y-axis: rotated -90deg on left side */
  .y-axis {
    left: 8px;
    top: 50%;
    transform: translate(-50%, -50%) rotate(-90deg);
  }

  /* Color axis: top center */
  .color-axis {
    top: 4px;
    left: 50%;
    transform: translateX(-50%);
  }
</style>
