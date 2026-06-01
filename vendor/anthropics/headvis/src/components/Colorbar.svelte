<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import { createAttentionColorScale } from '../lib/colors.js'

  let {
    maxValue = 1.0,
    width = 100,
    height = 12,
  } = $props()

  // Generate gradient stops
  let gradientStops = $derived.by(() => {
    const scale = createAttentionColorScale(maxValue)
    const stops = []
    const numStops = 20
    for (let i = 0; i <= numStops; i++) {
      const t = i / numStops
      const value = t * maxValue
      stops.push({
        offset: `${t * 100}%`,
        color: scale(value)
      })
    }
    return stops
  })

  // Unique ID for gradient
  let gradientId = $state(`colorbar-gradient-${Math.random().toString(36).slice(2)}`)
</script>

<div class="colorbar-container">
  <span class="label">activation</span>
  <span class="tick">0</span>
  <svg width={width} height={height}>
    <defs>
      <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
        {#each gradientStops as stop}
          <stop offset={stop.offset} stop-color={stop.color} />
        {/each}
      </linearGradient>
    </defs>
    <rect
      x="0"
      y="0"
      {width}
      {height}
      fill="url(#{gradientId})"
      stroke="#ccc"
      stroke-width="0.5"
    />
  </svg>
  <span class="tick">1</span>
</div>

<style>
  .colorbar-container {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .label {
    font-size: 11px;
    color: #666;
    text-transform: lowercase;
  }

  .tick {
    font-size: 10px;
    color: #666;
  }
</style>
