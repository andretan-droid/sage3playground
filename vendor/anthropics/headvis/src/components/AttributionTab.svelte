<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import { loadAttribution, updateManifestLocally } from '../lib/attributions.js'
  import { serverStore } from '../lib/stores.svelte.js'
  import FeaturePairList from './FeaturePairList.svelte'
  import FeaturePanel from './FeaturePanel.svelte'
  import SequenceDisplay from './SequenceDisplay.svelte'

  let {
    type = 'qk',  // 'qk' or 'ov'
    layer = 0,
    head = 0,
    sequence = null,  // Single sequence passed from store
    queryPos = null,  // Already selected
    keyPos = null,    // Already selected
    reductionMode = 'pairwise_max',
    transpose = false,
    nIntervals = 10,
    onClose = () => {},
  } = $props()

  // Attribution state
  let loading = $state(false)
  let error = $state(null)
  let data = $state(null)
  let selectedPairIdx = $state(null)

  // Load attribution when component mounts (positions already selected)
  async function loadData() {
    if (queryPos === null || keyPos === null || !sequence) return

    loading = true
    error = null

    try {
      const result = await loadAttribution(type, {
        layer,
        head,
        seqIdx: sequence.sequence_id,
        qpos: queryPos,
        kpos: keyPos,
      }, serverStore.config)

      if (result.source === 'none') {
        error = 'No server configured and no cached data'
      } else {
        data = result.data
        selectedPairIdx = data?.pairs?.length > 0 ? 0 : null
        // Update manifest only after successful load
        if (result.source === 'server') {
          updateManifestLocally(type, layer, head, sequence.sequence_id, queryPos, keyPos)
        }
      }
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  // Load data on mount
  $effect(() => {
    if (sequence && queryPos !== null && keyPos !== null) {
      loadData()
    }
  })

  // Marginal pair from FeaturePairList callback
  let marginalPair = $state(null)

  function handleMarginalPairChange(pair) {
    marginalPair = pair
  }

  // Get selected pair (from pairwise mode or marginal drill-down)
  let selectedPair = $derived.by(() => {
    // Check if marginal mode has a synthetic pair
    if (marginalPair) {
      return marginalPair
    }
    // Otherwise use pairwise selection
    if (data?.pairs && selectedPairIdx !== null) {
      return data.pairs[selectedPairIdx]
    }
    return null
  })

  // Labels based on type
  let sourceLabel = $derived(type === 'qk' ? 'Key' : 'Value')
  let targetLabel = $derived(type === 'qk' ? 'Query' : 'Output')

  // Draggable sequence section height
  let sequenceHeight = $state(200)
  let isDragging = $state(false)

  function startDrag(event) {
    isDragging = true
    const startY = event.clientY
    const startHeight = sequenceHeight

    function onMouseMove(e) {
      sequenceHeight = Math.max(40, startHeight + (e.clientY - startY))
    }
    function onMouseUp() {
      isDragging = false
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }

  // Draggable panel width
  let panelWidth = $state(280)

  function startPanelDrag(event) {
    const startX = event.clientX
    const startWidth = panelWidth

    function onMouseMove(e) {
      panelWidth = Math.max(160, Math.min(600, startWidth + (e.clientX - startX)))
    }
    function onMouseUp() {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }
</script>

<div class="attribution-tab">

  {#if sequence}
    <div class="sequence-section" style:height="{sequenceHeight}px">
      <div class="tokens-container">
        <SequenceDisplay
          {sequence}
          {reductionMode}
          {transpose}
          globalMaxActivation={1}
          {queryPos}
          {keyPos}
          attributionType={type}
        />
      </div>
      <div class="resize-handle" onmousedown={startDrag} role="separator" aria-orientation="horizontal">
        <svg width="20" height="6" viewBox="0 0 20 6">
          <line x1="2" y1="1" x2="18" y2="1" stroke="#999" stroke-width="1"/>
          <line x1="2" y1="4" x2="18" y2="4" stroke="#999" stroke-width="1"/>
        </svg>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <span>Loading attribution data...</span>
    </div>
  {:else if error}
    <div class="error-state">
      <span class="error-icon">⚠</span>
      <span>{error}</span>
      <button class="retry-btn" onclick={loadData}>Retry</button>
    </div>
  {:else if data?.pairs?.length > 0}
    <div class="attribution-content" style:grid-template-columns="{panelWidth}px 6px 1fr">
      <div class="left-panel">
        <FeaturePairList
          pairs={data.pairs}
          {sourceLabel}
          {targetLabel}
          bind:selectedIdx={selectedPairIdx}
          keyMarginals={data.key_marginals ?? []}
          queryMarginals={data.query_marginals ?? []}
          onMarginalPairChange={handleMarginalPairChange}
        />
      </div>
      <div class="panel-resize-handle" onmousedown={startPanelDrag} role="separator" aria-orientation="vertical"></div>
      <div class="right-panel">
        {#if selectedPair}
          <FeaturePanel
            pair={selectedPair}
            {sourceLabel}
            {targetLabel}
            {nIntervals}
          />
        {:else}
          <div class="no-selection">
            Select a feature pair to view details
          </div>
        {/if}
      </div>
    </div>
  {:else if data}
    <div class="empty-state">
      No feature pairs with non-zero attributions found
    </div>
  {/if}
</div>

<style>
  .attribution-tab {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #fafafa;
  }


  .sequence-section {
    background: white;
    border-bottom: 1px solid #ddd;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    position: relative;
    padding-top: 8px;
  }

  .tokens-container {
    overflow-y: auto;
    flex: 1;
  }

  .resize-handle {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 12px;
    cursor: ns-resize;
    background: #f5f5f5;
    border-top: 1px solid #eee;
    user-select: none;
  }

  .resize-handle:hover {
    background: #e8e8e8;
  }

  .attribution-content {
    display: grid;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .panel-resize-handle {
    cursor: ew-resize;
    background: #f0f0f0;
    border-left: 1px solid #e0e0e0;
    border-right: 1px solid #e0e0e0;
    user-select: none;
  }

  .panel-resize-handle:hover {
    background: #e0e0e0;
  }

  .left-panel {
    border-right: 1px solid #ddd;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .right-panel {
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .no-selection {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #999;
    font-size: 14px;
    font-style: italic;
  }

  .loading-state, .error-state, .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 40px;
    color: #666;
    font-size: 14px;
  }

  .error-state {
    color: #c00;
  }

  .error-icon {
    font-size: 20px;
  }

  .retry-btn {
    padding: 6px 12px;
    font-size: 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
    cursor: pointer;
  }

  .retry-btn:hover {
    background: #f5f5f5;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid #ddd;
    border-top-color: #666;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
