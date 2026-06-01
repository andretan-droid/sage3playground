<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import ScatterPlot from './ScatterPlot.svelte'

  let {
    config,
    scatterData = [],
    availableMetrics = [],
    selectedLayer = $bindable(0),
    selectedHead = $bindable(0),
    onScatterSelect = null,
    width = $bindable(350),
  } = $props()

  // Resize handling
  let isResizing = $state(false)
  let startX = $state(0)
  let startWidth = $state(0)

  function handleResizeStart(e) {
    isResizing = true
    startX = e.clientX
    startWidth = width
    document.addEventListener('mousemove', handleResizeMove)
    document.addEventListener('mouseup', handleResizeEnd)
    document.body.style.cursor = 'ew-resize'
    document.body.style.userSelect = 'none'
  }

  function handleResizeMove(e) {
    if (!isResizing) return
    const delta = e.clientX - startX
    const newWidth = Math.max(250, Math.min(600, startWidth + delta))
    width = newWidth
  }

  function handleResizeEnd() {
    isResizing = false
    document.removeEventListener('mousemove', handleResizeMove)
    document.removeEventListener('mouseup', handleResizeEnd)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  // Valid heads list from config: [[layer, head], ...]
  let validHeads = $derived(config?.heads ?? [])

  // Edit mode
  let isEditing = $state(false)
  let editIdx = $state(0)

  function startEditing() {
    editIdx = validHeads.findIndex(([l, h]) => l === selectedLayer && h === selectedHead)
    if (editIdx < 0) editIdx = 0
    isEditing = true
  }

  function confirmEdit() {
    const pair = validHeads[editIdx]
    if (pair) {
      selectedLayer = pair[0]
      selectedHead = pair[1]
    }
    isEditing = false
  }

  function handleEditKeydown(event) {
    if (event.key === 'Enter') {
      confirmEdit()
    } else if (event.key === 'Escape') {
      isEditing = false
    }
  }
</script>

<div class="sidebar" style="width: {width}px;">
  <div class="sidebar-content">
    <!-- Header -->
    <div class="sidebar-header">
      <div class="header-top">
        <h1 class="sidebar-title">Head Vis</h1>
      </div>

      <div class="model-name">
        Model: {config?.model_name ?? 'Loading...'}
      </div>

      <!-- Layer/Head display -->
      <div class="layer-head-section">
        {#if isEditing}
          <div class="layer-head-edit">
            <select
              class="head-select"
              bind:value={editIdx}
              onkeydown={handleEditKeydown}
            >
              {#each validHeads as [l, h], i}
                <option value={i}>L{l}H{h}</option>
              {/each}
            </select>
            <button class="confirm-button" onclick={confirmEdit}>OK</button>
          </div>
        {:else}
          <div class="layer-head-display">
            <span class="layer-head-text" ondblclick={startEditing}>Layer {selectedLayer} Head {selectedHead}</span>
            <button class="edit-button" onclick={startEditing}>Edit</button>
          </div>
        {/if}
      </div>
    </div>

    <!-- Scatter Plot -->
    <div class="scatter-container">
      <ScatterPlot
        data={scatterData}
        {selectedLayer}
        {selectedHead}
        {availableMetrics}
        scatterConfig={config?.scatter}
        dimensionsConfig={config?.dimensions}
        onSelect={onScatterSelect}
        containerWidth={width}
        aspectRatio={1.0}
      />
    </div>
  </div>
  <!-- Resize handle -->
  <div
    class="resize-handle"
    onmousedown={handleResizeStart}
    role="separator"
    aria-orientation="vertical"
  ></div>
</div>

<style>
  .sidebar {
    position: relative;
    border-right: 1px solid #ddd;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: #fafafa;
    font-family: system-ui, -apple-system, sans-serif;
    flex-shrink: 0;
  }

  .resize-handle {
    position: absolute;
    top: 0;
    right: 0;
    width: 6px;
    height: 100%;
    cursor: ew-resize;
    background: transparent;
    z-index: 10;
  }

  .resize-handle:hover {
    background: rgba(66, 133, 244, 0.3);
  }

  .sidebar-content {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }

  .sidebar-header {
    padding: 16px 16px 12px 16px;
    background: #fafafa;
    flex-shrink: 0;
  }

  .header-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
  }

  .sidebar-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
    color: #333;
  }

  .model-name {
    font-size: 13px;
    color: #666;
    margin-top: 4px;
  }

  .layer-head-section {
    margin-top: 16px;
  }

  .layer-head-display {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .layer-head-text {
    font-size: 16px;
    font-weight: 600;
    color: #333;
  }

  .edit-button {
    padding: 4px 10px;
    font-size: 12px;
    background: transparent;
    color: #4285f4;
    border: 1px solid #4285f4;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .edit-button:hover {
    background: #4285f4;
    color: white;
  }

  .layer-head-edit {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #333;
  }

  .head-select {
    font-size: 13px;
    font-weight: 600;
    border: 1px solid #ddd;
    background: white;
    outline: none;
    font-family: inherit;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
  }

  .head-select:focus {
    border-color: #4285f4;
    box-shadow: 0 0 0 2px rgba(66, 133, 244, 0.1);
  }

  .confirm-button {
    padding: 4px 10px;
    font-size: 12px;
    background: #4285f4;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .confirm-button:hover {
    background: #3367d6;
  }

  .scatter-container {
    flex-shrink: 0;
    padding: 0 16px 16px 16px;
  }
</style>
