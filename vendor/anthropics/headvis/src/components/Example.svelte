<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import Token from './Token.svelte'
  import { createSparse, getRowMax, getColMax } from '../lib/sparse.js'
  import { computeReduction } from '../lib/reductions.js'
  import { getAttentionColor } from '../lib/colors.js'
  import { attributionStore } from '../lib/stores.svelte.js'
  import { getSequenceCacheStatus, getCachedQueryPositions, getCachedKeyPositions } from '../lib/attributions.js'
  let {
    sequence,
    reductionMode = 'pairwise_max',
    transpose = false,
    globalMaxActivation = 1.0,
    layer = 0,
    head = 0,
    onAttributionComplete = null,  // Called when attribution is ready, switches to tab
    onDelete = null,               // async (sequenceId) => void — shows x button if set
    umapAvailable = false,
    hasServer = false,
    onUmapProjection = null,       // (sequence, queryPos, keyPos) => void — fires UMAP projection
  } = $props()

  let deleting = $state(false)
  let copySuccess = $state(false)

  async function copySequenceText() {
    const text = sequence.tokens.join('')
    try {
      await navigator.clipboard.writeText(text)
      copySuccess = true
      setTimeout(() => { copySuccess = false }, 1500)
    } catch {
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
      copySuccess = true
      setTimeout(() => { copySuccess = false }, 1500)
    }
  }

  async function handleDelete() {
    if (!onDelete || deleting) return
    deleting = true
    try {
      await onDelete(sequence.sequence_id)
    } finally {
      deleting = false
    }
  }

  // Attribution mode state (local to this component while selecting tokens)
  let attributionMode = $state(null)  // null, 'qk', 'ov', or 'umap'
  let queryPos = $state(null)
  let keyPos = $state(null)

  // Cache awareness — which tokens/pairs have precomputed attributions
  let cacheStatus = $derived(getSequenceCacheStatus(layer, head, sequence.sequence_id))
  let cachedQueries = $derived(
    attributionMode ? getCachedQueryPositions(layer, head, sequence.sequence_id, attributionMode) : new Set()
  )
  let cachedKeys = $derived(
    attributionMode && queryPos !== null
      ? getCachedKeyPositions(layer, head, sequence.sequence_id, attributionMode, queryPos)
      : new Set()
  )

  // Create sparse tensor from sequence data
  let sparse = $derived(createSparse(
    sequence.attention_indices,
    sequence.attention_values,
    sequence.seq_len
  ))

  // Hovered token index for hover mode
  let hoveredIdx = $state(null)

  // In attribution mode, force 'max' reduction mode (max over queries)
  // This shows which query positions have strong attention, helping user pick good pairs
  let effectiveReductionMode = $derived(attributionMode ? 'max' : reductionMode)

  // In attribution mode after query selection, show attention from the selected query
  // This helps the user pick a key with strong attention
  let effectiveHoveredIdx = $derived(
    attributionMode && queryPos !== null && keyPos === null
      ? queryPos  // Show attention from selected query
      : hoveredIdx  // Normal hover behavior
  )

  // Compute reduced activations based on mode (used for coloring)
  let reduction = $derived(computeReduction(sparse, effectiveReductionMode, effectiveHoveredIdx, transpose))

  // Compute row/col max for consistent tooltip values in max mode
  // This ensures tooltip always shows max attention, not self-attention during hover
  let tooltipActivations = $derived(
    effectiveReductionMode === 'max'
      ? (transpose ? getColMax(sparse) : getRowMax(sparse))
      : reduction.activations
  )

  // Use globalMaxActivation for color normalization across all sequences
  // This ensures lower intervals have weaker colors relative to the highest interval

  // Build tokens with colors
  // In attribution mode, keep showing attention colors to guide selection
  let tokens = $derived(sequence.tokens.map((text, i) => ({
    text,
    index: i,
    activation: tooltipActivations[i],  // Tooltip shows consistent max value
    color: getAttentionColor(reduction.activations[i], globalMaxActivation),
    isAssociated: !attributionMode && reduction.pairInfo?.keyIdx === i,
    isQuerySelected: i === queryPos,
    isKeySelected: i === keyPos,
    isCachedQuery: attributionMode && queryPos === null && cachedQueries.has(i),
    isCachedKey: attributionMode && queryPos !== null && cachedKeys.has(i),
  })))

  function handleHover(idx) {
    // Hover behavior is active in 'max' mode - shows attention pattern for hovered token
    if (reductionMode === 'max' && !attributionMode) {
      hoveredIdx = idx
    }
  }

  function enterAttributionMode(mode) {
    attributionMode = mode
    queryPos = null
    keyPos = null
  }

  function exitAttributionMode() {
    attributionMode = null
    queryPos = null
    keyPos = null
  }

  function handleTokenClick(idx) {
    if (!attributionMode) return

    if (queryPos === null) {
      queryPos = idx
    } else if (keyPos === null) {
      keyPos = idx
      const mode = attributionMode
      const q = queryPos
      const k = idx
      // Clear mode state first (same for all modes)
      attributionMode = null
      queryPos = null
      keyPos = null
      // Dispatch based on mode
      if (mode === 'umap') {
        if (onUmapProjection) onUmapProjection(sequence, q, k)
      } else {
        attributionStore.setAttribution(sequence, mode, q, k)
        if (onAttributionComplete) onAttributionComplete(mode)
      }
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Escape' && attributionMode) {
      exitAttributionMode()
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="example">
  <div class="header">
    <div class="meta">
      <span class="sequence-id" class:copied={copySuccess} title="Copy sequence text" onclick={copySequenceText}>
        {#if copySuccess}
          Copied Sequence
        {:else}
          {sequence.sequence_id}
        {/if}
      </span>
      <span class="max-act">max: {sequence.max_activation.toFixed(3)}</span>
      {#if attributionMode}
        <span class="mode-indicator" class:qk={attributionMode === 'qk'} class:ov={attributionMode === 'ov'} class:umap={attributionMode === 'umap'}>
          {attributionMode.toUpperCase()} Mode
          {#if queryPos === null}
            - Click query token
          {:else if keyPos === null}
            - Click key token
          {/if}
        </span>
      {/if}
    </div>
    <div class="operations">
      {#if attributionMode}
        <button class="op-btn cancel-btn" onclick={exitAttributionMode}>Cancel</button>
      {:else}
        <button class="op-btn qk-btn" class:cached={cacheStatus.qk} onclick={() => enterAttributionMode('qk')} title="QK Attribution">QK</button>
        <button class="op-btn ov-btn" class:cached={cacheStatus.ov} onclick={() => enterAttributionMode('ov')} title="OV Attribution">OV</button>
        {#if umapAvailable}
          <button class="op-btn umap-btn" onclick={() => enterAttributionMode('umap')} disabled={!hasServer} title="Project to UMAP">UMAP</button>
        {/if}
        {#if onDelete}
          <button class="op-btn delete-btn" onclick={handleDelete} disabled={deleting} title="Delete sequence">
            {deleting ? '...' : '\u00d7'}
          </button>
        {/if}
      {/if}
    </div>
  </div>
  <div class="tokens" class:clickable={attributionMode}
       onmouseleave={() => hoveredIdx = null} role="presentation">
    {#each tokens as token (token.index)}
      <Token
        text={token.text}
        color={token.color}
        isAssociated={token.isAssociated}
        index={token.index}
        activation={attributionMode ? null : token.activation}
        onHover={handleHover}
        onClick={attributionMode ? handleTokenClick : null}
        isQuerySelected={token.isQuerySelected}
        isKeySelected={token.isKeySelected}
        attributionType={attributionMode}
        isCached={token.isCachedQuery || token.isCachedKey}
      />
    {/each}
  </div>
</div>


<style>
  .example {
    margin-bottom: 10px;
    background: white;
    border-left: 3px solid transparent;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 10px;
    border-bottom: 1px solid #e0e0e0;
    flex-wrap: nowrap;
    overflow: hidden;
    gap: 4px;
  }

  .meta {
    display: flex;
    gap: 12px;
    font-size: 11px;
    color: #666;
    align-items: center;
  }

  .sequence-id {
    font-family: monospace;
    font-weight: 500;
    background: #e0e0e0;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 20px;
    text-align: center;
  }

  .sequence-id:hover {
    background: #bdbdbd;
  }

  .sequence-id.copied {
    background: #4caf50;
    color: white;
  }

  .max-act {
    font-family: monospace;
  }

  .operations {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .op-btn {
    padding: 2px 6px;
    font-size: 10px;
    border: 1px solid #ddd;
    border-radius: 3px;
    background: #f8f8f8;
    color: #666;
    cursor: not-allowed;
    opacity: 0.6;
  }

  .op-btn:not(:disabled) {
    cursor: pointer;
    opacity: 1;
  }

  .op-btn:not(:disabled):hover {
    background: #e8e8e8;
  }

  .op-btn.qk-btn, .op-btn.ov-btn, .op-btn.umap-btn {
    cursor: pointer;
    opacity: 1;
  }

  .op-btn.qk-btn {
    border-color: #1565c0;
    color: #1565c0;
  }

  .op-btn.qk-btn:hover {
    background: #e3f2fd;
  }

  .op-btn.qk-btn.cached {
    background: #1565c0;
    color: white;
  }

  .op-btn.qk-btn.cached:hover {
    background: #0d47a1;
  }

  .op-btn.ov-btn {
    border-color: #c2185b;
    color: #c2185b;
  }

  .op-btn.ov-btn:hover {
    background: #fce4ec;
  }

  .op-btn.ov-btn.cached {
    background: #c2185b;
    color: white;
  }

  .op-btn.ov-btn.cached:hover {
    background: #ad1457;
  }

  .op-btn.umap-btn {
    border-color: #2e7d32;
    color: #2e7d32;
  }

  .op-btn.umap-btn:hover {
    background: #e8f5e9;
  }

  .op-btn.cancel-btn {
    cursor: pointer;
    opacity: 1;
    border-color: #666;
    color: #666;
  }

  .op-btn.cancel-btn:hover {
    background: #eee;
  }

  .op-btn.delete-btn {
    cursor: pointer;
    opacity: 1;
    border-color: #c62828;
    color: #c62828;
    font-size: 14px;
    line-height: 1;
    padding: 1px 5px;
  }

  .op-btn.delete-btn:hover:not(:disabled) {
    background: #ffebee;
  }

  .mode-indicator {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    animation: pulse 1.5s ease-in-out infinite;
  }

  .mode-indicator.qk {
    background: #e3f2fd;
    color: #1565c0;
  }

  .mode-indicator.ov {
    background: #fce4ec;
    color: #c2185b;
  }

  .mode-indicator.umap {
    background: rgba(46, 125, 50, 0.1);
    color: #2e7d32;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }

  .tokens.clickable {
    cursor: pointer;
  }

  .tokens {
    line-height: 2;
    font-size: 0;
    padding: 10px;
    white-space: normal;
    overflow-wrap: break-word;
    word-wrap: break-word;
  }
</style>
