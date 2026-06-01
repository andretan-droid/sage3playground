<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  let {
    pairs = [],
    sourceLabel = 'Key',
    targetLabel = 'Query',
    selectedIdx = $bindable(null),
    keyMarginals = [],
    queryMarginals = [],
    onMarginalPairChange = null,
    initialViewMode = 'pairs',
    onSelect = null,
  } = $props()

  // View mode: 'pairs', 'key-marginal', 'query-marginal'
  let viewMode = $state(initialViewMode)

  // Selected marginal feature index (for drill-down)
  let selectedMarginalIdx = $state(null)

  // Reset all selections when switching modes
  $effect(() => {
    viewMode;
    selectedMarginalIdx = null
    selectedIdx = null
    if (onMarginalPairChange) onMarginalPairChange(null)
  })

  // Max absolute score for color scaling (per-mode)
  let maxAbsScore = $derived.by(() => {
    if (viewMode === 'pairs') {
      return Math.max(...pairs.map(p => Math.abs(p.attribution)), 0.001)
    } else if (viewMode === 'key-marginal') {
      if (selectedMarginalIdx !== null && keyMarginals[selectedMarginalIdx]) {
        const interactions = keyMarginals[selectedMarginalIdx].top_interactions
        return Math.max(...interactions.map(i => Math.abs(i.pairwise_score)), 0.001)
      }
      return Math.max(...keyMarginals.map(m => Math.abs(m.marginal_score)), 0.001)
    } else {
      if (selectedMarginalIdx !== null && queryMarginals[selectedMarginalIdx]) {
        const interactions = queryMarginals[selectedMarginalIdx].top_interactions
        return Math.max(...interactions.map(i => Math.abs(i.pairwise_score)), 0.001)
      }
      return Math.max(...queryMarginals.map(m => Math.abs(m.marginal_score)), 0.001)
    }
  })

  function getColor(score) {
    const magnitude = Math.abs(score) / maxAbsScore
    if (score >= 0) {
      return `rgba(255, 140, 0, ${magnitude})`
    } else {
      return `rgba(100, 149, 237, ${magnitude})`
    }
  }

  function handlePairClick(idx) {
    selectedIdx = idx
    if (onSelect) onSelect()
  }

  function handleMarginalClick(idx) {
    selectedMarginalIdx = idx
    // Also select the first pair so the detail panel shows something
    selectedIdx = null
    if (onSelect) onSelect()
  }

  function handleInteractionClick(marginalIdx, interactionIdx) {
    // Signal to parent which pair to show (build a synthetic pair)
    selectedMarginalIdx = marginalIdx
    if (onSelect) onSelect()
    selectedIdx = interactionIdx
  }

  function handleKeydown(event) {
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      if (viewMode === 'pairs') {
        if (selectedIdx > 0) selectedIdx--
      }
      document.activeElement?.blur()
    } else if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (viewMode === 'pairs') {
        if (selectedIdx < pairs.length - 1) selectedIdx++
      }
      document.activeElement?.blur()
    }
  }

  let hasMarginals = $derived(keyMarginals.length > 0 || queryMarginals.length > 0)

  // Notify parent when marginal selection changes
  $effect(() => {
    const pair = marginalSelectedPair
    if (onMarginalPairChange) onMarginalPairChange(pair)
  })

  // For marginal modes, build the selected pair data for the detail panel
  // This is exposed via $derived so the parent AttributionTab can access it
  // Shows single feature when only marginal is selected, full pair when interaction is also selected
  let marginalSelectedPair = $derived.by(() => {
    if (viewMode === 'key-marginal' && selectedMarginalIdx !== null) {
      const marginal = keyMarginals[selectedMarginalIdx]
      if (!marginal) return null
      if (selectedIdx !== null) {
        const interaction = marginal.top_interactions?.[selectedIdx]
        if (interaction) {
          return {
            key_description: marginal.description,
            key_snippets: marginal.snippets,
            query_description: interaction.description,
            query_snippets: interaction.snippets,
            attribution: interaction.pairwise_score,
          }
        }
      }
      // Single feature selected, no interaction yet
      return {
        key_description: marginal.description,
        key_snippets: marginal.snippets,
        query_description: null,
        query_snippets: [],
        attribution: marginal.marginal_score,
        singleFeatureSide: 'key',
      }
    } else if (viewMode === 'query-marginal' && selectedMarginalIdx !== null) {
      const marginal = queryMarginals[selectedMarginalIdx]
      if (!marginal) return null
      if (selectedIdx !== null) {
        const interaction = marginal.top_interactions?.[selectedIdx]
        if (interaction) {
          return {
            query_description: marginal.description,
            query_snippets: marginal.snippets,
            key_description: interaction.description,
            key_snippets: interaction.snippets,
            attribution: interaction.pairwise_score,
          }
        }
      }
      // Single feature selected, no interaction yet
      return {
        query_description: marginal.description,
        query_snippets: marginal.snippets,
        key_description: null,
        key_snippets: [],
        attribution: marginal.marginal_score,
        singleFeatureSide: 'query',
      }
    }
    return null
  })
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="pair-list">
  <!-- Mode tabs -->
  {#if hasMarginals}
    <div class="mode-tabs">
      <button
        class="mode-tab"
        class:active={viewMode === 'pairs'}
        onclick={() => viewMode = 'pairs'}
      >Pairs</button>
      <button
        class="mode-tab"
        class:active={viewMode === 'key-marginal'}
        class:disabled={keyMarginals.length === 0}
        onclick={() => { if (keyMarginals.length > 0) viewMode = 'key-marginal' }}
      >Marginal {sourceLabel}</button>
      <button
        class="mode-tab"
        class:active={viewMode === 'query-marginal'}
        class:disabled={queryMarginals.length === 0}
        onclick={() => { if (queryMarginals.length > 0) viewMode = 'query-marginal' }}
      >Marginal {targetLabel}</button>
    </div>
  {/if}

  {#if viewMode === 'pairs'}
    <!-- Pairwise view (existing) -->
    <div class="list-header">
      <div class="header-col source">{sourceLabel}</div>
      <div class="header-col target">{targetLabel}</div>
    </div>
    <div class="list-content">
      {#each pairs as pair, idx (idx)}
        <button
          class="pair-item"
          class:selected={selectedIdx === idx}
          style:background-color={getColor(pair.attribution)}
          onclick={() => handlePairClick(idx)}
        >
          <div class="pair-col source" title={pair.key_description || ''}>
            {pair.key_description || '—'}
          </div>
          <div class="pair-col target" title={pair.query_description || ''}>
            {pair.query_description || '—'}
          </div>
        </button>
      {/each}
    </div>

  {:else if viewMode === 'key-marginal'}
    <!-- Key marginal view -->
    <div class="list-header">
      <div class="header-col source">{sourceLabel} (marginal)</div>
      <div class="header-col target">
        {#if selectedMarginalIdx !== null}
          Top {targetLabel} interactions
        {/if}
      </div>
    </div>
    <div class="list-content dual">
      <div class="marginal-column">
        {#each keyMarginals as marginal, idx (idx)}
          <button
            class="pair-item single"
            class:selected={selectedMarginalIdx === idx}
            style:background-color={selectedMarginalIdx === null ? getColor(marginal.marginal_score) : (selectedMarginalIdx === idx ? '#e3f2fd' : 'transparent')}
            onclick={() => handleMarginalClick(idx)}
            title={marginal.description || ''}
          >
            <div class="pair-col source">
              {marginal.description || '—'}
            </div>
            <div class="marginal-score">{marginal.marginal_score >= 0 ? '+' : ''}{marginal.marginal_score.toFixed(2)}</div>
          </button>
        {/each}
      </div>
      <div class="interaction-column">
        {#if selectedMarginalIdx !== null && keyMarginals[selectedMarginalIdx]}
          {#each keyMarginals[selectedMarginalIdx].top_interactions as interaction, idx (idx)}
            <button
              class="pair-item single"
              class:selected={selectedIdx === idx}
              style:background-color={getColor(interaction.pairwise_score)}
              onclick={() => handleInteractionClick(selectedMarginalIdx, idx)}
              title={interaction.description || ''}
            >
              <div class="pair-col source">
                {interaction.description || '—'}
              </div>
            </button>
          {/each}
        {:else}
          <div class="empty-hint">Select a {sourceLabel.toLowerCase()} feature</div>
        {/if}
      </div>
    </div>

  {:else if viewMode === 'query-marginal'}
    <!-- Query marginal view -->
    <div class="list-header">
      <div class="header-col source">
        {#if selectedMarginalIdx !== null}
          Top {sourceLabel} interactions
        {/if}
      </div>
      <div class="header-col target">{targetLabel} (marginal)</div>
    </div>
    <div class="list-content dual">
      <div class="interaction-column">
        {#if selectedMarginalIdx !== null && queryMarginals[selectedMarginalIdx]}
          {#each queryMarginals[selectedMarginalIdx].top_interactions as interaction, idx (idx)}
            <button
              class="pair-item single"
              class:selected={selectedIdx === idx}
              style:background-color={getColor(interaction.pairwise_score)}
              onclick={() => handleInteractionClick(selectedMarginalIdx, idx)}
              title={interaction.description || ''}
            >
              <div class="pair-col source">
                {interaction.description || '—'}
              </div>
            </button>
          {/each}
        {:else}
          <div class="empty-hint">Select a {targetLabel.toLowerCase()} feature</div>
        {/if}
      </div>
      <div class="marginal-column">
        {#each queryMarginals as marginal, idx (idx)}
          <button
            class="pair-item single"
            class:selected={selectedMarginalIdx === idx}
            style:background-color={selectedMarginalIdx === null ? getColor(marginal.marginal_score) : (selectedMarginalIdx === idx ? '#e3f2fd' : 'transparent')}
            onclick={() => handleMarginalClick(idx)}
            title={marginal.description || ''}
          >
            <div class="pair-col source" style="text-align: right;">
              {marginal.description || '—'}
            </div>
            <div class="marginal-score">{marginal.marginal_score >= 0 ? '+' : ''}{marginal.marginal_score.toFixed(2)}</div>
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .pair-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: white;
  }

  .mode-tabs {
    display: flex;
    gap: 2px;
    padding: 4px 6px;
    background: #f0f0f0;
    border-bottom: 1px solid #ddd;
    flex-shrink: 0;
  }

  .mode-tab {
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 500;
    border: 1px solid #ccc;
    border-radius: 3px;
    background: white;
    color: #666;
    cursor: pointer;
    transition: all 0.15s;
  }

  .mode-tab:hover:not(.disabled) {
    background: #e8e8e8;
  }

  .mode-tab.active {
    background: #333;
    color: white;
    border-color: #333;
  }

  .mode-tab.disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .list-header {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 8px;
    padding: 4px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #ddd;
    flex-shrink: 0;
  }

  .header-col {
    font-size: 10px;
    font-weight: 600;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .header-col.target {
    text-align: right;
  }

  .list-content {
    flex: 1;
    overflow-y: auto;
    padding: 4px;
  }

  .list-content.dual {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 4px;
    overflow: hidden;
  }

  .marginal-column, .interaction-column {
    overflow-y: auto;
    padding: 2px;
  }

  .pair-item {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 8px;
    padding: 6px 8px;
    margin-bottom: 2px;
    border: 2px solid transparent;
    border-radius: 0;
    cursor: pointer;
    font-size: 11px;
    width: 100%;
    text-align: left;
    transition: border-color 0.15s;
  }

  .pair-item.single {
    grid-template-columns: 1fr auto;
    gap: 0 4px;
  }

  .pair-item:hover {
    opacity: 0.9;
  }

  .pair-item:focus {
    outline: none;
  }

  .pair-item.selected {
    border-color: #5064b4;
  }

  .pair-col {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .pair-col.source {
    color: #333;
  }

  .pair-col.target {
    text-align: right;
    color: #333;
    padding-left: 6px;
  }

  .marginal-score {
    font-family: monospace;
    font-size: 9px;
    color: #888;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .empty-hint {
    padding: 20px;
    text-align: center;
    color: #999;
    font-size: 11px;
    font-style: italic;
  }
</style>
