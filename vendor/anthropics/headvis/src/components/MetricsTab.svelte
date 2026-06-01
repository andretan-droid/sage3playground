<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import * as d3 from 'd3'
  import TokenRankTable from './TokenRankTable.svelte'
  import LinePlot from './LinePlot.svelte'

  let {
    headMetrics = null,
    rawData = null,
    config = null,
  } = $props()

  // Extract data from rawData
  let histogram = $derived(rawData?.histogram || null)
  let statistics = $derived(rawData?.statistics || null)
  let sequences = $derived(rawData?.sequences || [])
  let statisticsDisplay = $derived(config?.statistics_display || null)
  let customPlots = $derived(config?.custom_plots || [])
  let customTables = $derived(config?.custom_tables || [])

  // Use pre-computed histogram if available, otherwise compute from sequences
  let activationHistogram = $derived.by(() => {
    if (histogram && histogram.bin_values && histogram.bin_edges) {
      const binEdges = histogram.bin_edges
      const binValues = histogram.bin_values
      const bins = []
      for (let i = 0; i < binValues.length; i++) {
        bins.push({
          x0: binEdges[i],
          x1: binEdges[i + 1] || binEdges[i],
          length: binValues[i]
        })
      }
      return {
        bins,
        maxCount: d3.max(binValues),
        extent: [binEdges[0], binEdges[binEdges.length - 1]],
        isPrecomputed: true,
        totalCount: d3.sum(binValues)
      }
    }

    if (!sequences || sequences.length === 0) return null
    const values = sequences.map(s => s.max_activation).filter(v => v != null)
    if (values.length === 0) return null
    const extent = d3.extent(values)
    const bins = d3.bin().domain(extent).thresholds(20)(values)
    return {
      bins,
      maxCount: d3.max(bins, d => d.length),
      extent,
      isPrecomputed: false,
      totalCount: values.length
    }
  })

  // Log scale height calculation
  function logHeight(value, maxValue) {
    if (value <= 0) return 0
    const logValue = Math.log10(value + 1)
    const logMax = Math.log10(maxValue + 1)
    return (logValue / logMax) * 100
  }

  // Generate y-axis ticks for log scale
  let yAxisTicks = $derived.by(() => {
    if (!activationHistogram) return []
    const maxCount = activationHistogram.maxCount
    const ticks = []
    let power = 0
    while (Math.pow(10, power) <= maxCount) {
      ticks.push(Math.pow(10, power))
      power++
    }
    return ticks
  })

  // Check if a custom plot has valid data
  function hasPlotData(plotConfig) {
    if (!rawData) return false
    const data = rawData[plotConfig.key]
    return data && data.bin_values && data.bin_edges
  }

  function formatValue(value) {
    if (value == null) return '-'
    if (typeof value !== 'number') return String(value)
    if (Math.abs(value) < 0.001) return value.toExponential(2)
    if (Math.abs(value) >= 1000) return value.toExponential(2)
    return value.toFixed(4)
  }

  // Format statistic value based on format type from config
  function formatStatistic(value, format) {
    if (value == null) return '-'
    if (typeof value !== 'number') return String(value)
    switch (format) {
      case 'percent':
        return (value * 100).toFixed(1) + '%'
      case 'integer':
        return Math.round(value).toString()
      case 'scientific':
        return value.toExponential(2)
      default:
        return formatValue(value)
    }
  }

  function getXTicks(extent, count = 5) {
    if (!extent || extent[0] === extent[1]) return []
    const [min, max] = extent
    return Array.from({ length: count + 1 }, (_, i) => min + (max - min) * (i / count))
  }

  function formatCount(count) {
    if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
    if (count >= 1000) return (count / 1000).toFixed(1) + 'k'
    return count.toString()
  }


</script>

<div class="metrics-tab">
  <!-- 1. Max Activation Distribution (always first) -->
  {#if activationHistogram}
    <section class="plot-section">
      <h3>Max Activation Distribution</h3>
      <p class="plot-info">
        {#if activationHistogram.isPrecomputed}
          {formatCount(activationHistogram.totalCount)} activations (all data)
        {:else}
          {activationHistogram.totalCount} sequences (visible only)
        {/if}
        &mdash; range: [{activationHistogram.extent[0].toFixed(3)}, {activationHistogram.extent[1].toFixed(3)}]
      </p>
      <div class="plot-wrapper">
        <div class="y-axis">
          {#each yAxisTicks as tick}
            <div class="y-tick" style:bottom="{logHeight(tick, activationHistogram.maxCount)}%">
              <span class="y-label">{formatCount(tick)}</span>
            </div>
          {/each}
        </div>
        <div class="plot-area histogram-bars">
          {#each activationHistogram.bins as bin}
            <div
              class="bar-container"
              title="{bin.x0.toFixed(4)} - {bin.x1.toFixed(4)}: {formatCount(bin.length)}"
            >
              <div
                class="bar activation-bar"
                style:height="{logHeight(bin.length, activationHistogram.maxCount)}%"
              ></div>
            </div>
          {/each}
        </div>
      </div>
      <div class="plot-axis">
        {#each getXTicks(activationHistogram.extent) as tick}
          <span>{tick.toFixed(2)}</span>
        {/each}
      </div>
    </section>
  {/if}

  <!-- 2. Custom plots (config-driven) — all use LinePlot -->
  {#each customPlots as plotConfig (plotConfig.key)}
    {#if hasPlotData(plotConfig)}
      <section class="plot-section">
        <h3>{plotConfig.label}</h3>
        {#if plotConfig.description}
          <p class="plot-info">{plotConfig.description}</p>
        {/if}
        <LinePlot
          values={rawData[plotConfig.key].bin_values}
          edges={rawData[plotConfig.key].bin_edges}
          xFormat={plotConfig.x_format}
        />
      </section>
    {/if}
  {/each}

  <!-- 2. Custom tables (config-driven) -->
  {#if customTables.length > 0}
    {@const visibleTables = customTables.filter(t => rawData?.[t.key]?.length > 0)}
    {#if visibleTables.length > 0}
      <section class="token-tables-section">
        <div class="token-tables">
          {#each visibleTables as tableConfig (tableConfig.key)}
            {@const tableData = rawData[tableConfig.key]}
            <div class="token-table">
              <h3>{tableConfig.label}</h3>
              {#if tableConfig.description}
                <p class="token-table-info">{tableConfig.description}</p>
              {/if}
              <TokenRankTable items={tableData} maxRows={tableConfig.max_rows || 15} />
            </div>
          {/each}
        </div>
      </section>
    {/if}
  {/if}

  <!-- 3. Activation statistics -->
  <section class="statistics-section">
    <h3>Activation Statistics</h3>
    {#if statistics && Object.keys(statistics).length > 0}
      <table>
        <tbody>
          {#each Object.entries(statistics) as [key, value]}
            {#if value != null}
              <tr>
                <td class="metric-name">{statisticsDisplay?.[key]?.label || key}</td>
                <td class="metric-value">{formatStatistic(value, statisticsDisplay?.[key]?.format)}</td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    {:else if sequences.length > 0}
      <table>
        <tbody>
          <tr>
            <td class="metric-name">Sequences shown</td>
            <td class="metric-value">{sequences.length}</td>
          </tr>
          <tr>
            <td class="metric-name">Avg max activation</td>
            <td class="metric-value">{formatValue(d3.mean(sequences, s => s.max_activation))}</td>
          </tr>
          <tr>
            <td class="metric-name">Max activation</td>
            <td class="metric-value">{formatValue(d3.max(sequences, s => s.max_activation))}</td>
          </tr>
        </tbody>
      </table>
    {:else}
      <p class="empty-note">No statistics available</p>
    {/if}
  </section>

  <!-- 4. Head metrics -->
  {#if headMetrics}
    <section class="metrics-table">
      <h3>Head Metrics</h3>
      <table>
        <tbody>
          {#each Object.entries(headMetrics) as [key, value]}
            <tr>
              <td class="metric-name">{key}</td>
              <td class="metric-value">{formatValue(value)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  {#if !headMetrics && !rawData}
    <div class="empty">No metrics data available</div>
  {/if}
</div>

<style>
  .metrics-tab {
    padding: 16px;
    overflow-y: auto;
    max-height: calc(100vh - 200px);
  }

  section {
    margin-bottom: 24px;
    background: white;
    border: 1px solid #eee;
    border-radius: 4px;
    padding: 16px;
  }

  h3 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: #333;
    font-weight: 600;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  tr:not(:last-child) td {
    border-bottom: 1px solid #f0f0f0;
  }

  td {
    padding: 8px 0;
  }

  .metric-name {
    color: #666;
    font-size: 13px;
  }

  .metric-value {
    font-family: monospace;
    font-size: 13px;
    text-align: right;
    color: #333;
  }

  .plot-info {
    margin: 0 0 12px 0;
    font-size: 12px;
    color: #666;
  }

  .plot-wrapper {
    display: flex;
    gap: 4px;
  }

  .y-axis {
    position: relative;
    width: 32px;
    height: 100px;
    flex-shrink: 0;
  }

  .y-tick {
    position: absolute;
    right: 0;
    transform: translateY(50%);
    display: flex;
    align-items: center;
  }

  .y-label {
    font-size: 9px;
    color: #888;
    font-family: monospace;
    text-align: right;
    width: 100%;
  }

  .plot-area {
    display: flex;
    align-items: flex-end;
    height: 100px;
    background: #fafafa;
    border-radius: 4px;
    padding: 8px;
    flex: 1;
    position: relative;
  }

  .plot-area.histogram-bars {
    gap: 2px;
  }


  .bar-container {
    flex: 1;
    height: 100%;
    display: flex;
    align-items: flex-end;
  }

  .bar {
    width: 100%;
    background: linear-gradient(to top, #4285f4, #7baaf7);
    border-radius: 2px 2px 0 0;
    min-height: 2px;
    transition: height 0.2s ease;
  }

  .bar.activation-bar {
    background: linear-gradient(to top, #ff9800, #ffb74d);
  }

  .bar-container:hover .bar {
    opacity: 0.8;
  }

  .plot-axis {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    margin-left: 36px;
    font-size: 11px;
    color: #888;
    font-family: monospace;
  }

  .empty {
    color: #999;
    text-align: center;
    padding: 40px;
  }

  .empty-note {
    color: #999;
    font-size: 13px;
    margin: 0;
  }

  .token-tables-section {
    /* Token tables section */
  }

  .token-tables {
    display: flex;
    gap: 16px;
  }

  .token-table {
    flex: 1;
    min-width: 0;
  }

  .token-table h3 {
    margin: 0 0 4px 0;
  }

  .token-table-info {
    margin: 0 0 12px 0;
    font-size: 11px;
    color: #888;
  }


</style>
