<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import Example from './Example.svelte'
  import AddSequenceForm from './AddSequenceForm.svelte'
  import { serverStore } from '../lib/stores.svelte.js'

  let {
    sequences = [],
    customSequences = [],
    reductionMode = $bindable('pairwise_max'),
    transpose = false,
    selectedInterval = $bindable(null),
    nIntervals = 10,
    layer = 0,
    head = 0,
    onAttributionComplete = null,  // Called when attribution selection completes
    onAddCustomSequence = null,    // async (text) => void
    onDeleteCustomSequence = null, // async (sequenceId) => void
    umapAvailable = false,
    onUmapProjection = null,       // (sequence, queryPos, keyPos) => void
  } = $props()

  let hasServer = $derived(serverStore.isConfigured)

  // Filter by interval if selected (-1 = custom sequences)
  let showingCustom = $derived(selectedInterval === -1)

  let filteredSequences = $derived(
    showingCustom
      ? customSequences
      : selectedInterval !== null
        ? sequences.filter(s => s.interval === selectedInterval)
        : sequences
  )

  // Sort by max activation (highest first)
  let sortedSequences = $derived(
    [...filteredSequences].sort((a, b) => b.max_activation - a.max_activation)
  )

  // Global max across ALL dataset sequences for consistent color normalization.
  // Custom sequences use the same scale so they're visually comparable.
  let globalMaxActivation = $derived(
    Math.max(...sequences.map(s => s.max_activation), 0.001)
  )

  // Generate interval options (highest first, with Custom at top if available)
  let intervalOptions = $derived(
    Array.from({ length: nIntervals }, (_, i) => nIntervals - i)
  )

  let isAddFormExpanded = $state(false)
</script>

<div class="sequences-tab">
  <!-- Controls bar -->
  <div class="controls-bar">
    <div class="control-group">
      <label>Interval:</label>
      <select bind:value={selectedInterval}>
        {#if customSequences.length > 0 || hasServer}
          <option value={-1}>Custom ({customSequences.length})</option>
        {/if}
        {#each intervalOptions as interval}
          <option value={interval}>{interval} of {nIntervals}</option>
        {/each}
      </select>
    </div>

    <div class="control-group">
      <label>Reduction:</label>
      <select bind:value={reductionMode}>
        <option value="pairwise_max">pairwise max</option>
        <option value="max">max</option>
      </select>
      <span class="reduction-hint">
        {#if reductionMode === 'max'}
          (over {transpose ? 'queries' : 'keys'})
        {:else}
          (highlights strongest Q→K pair)
        {/if}
      </span>
    </div>

    {#if showingCustom && hasServer}
      <button class="add-button" onclick={() => isAddFormExpanded = !isAddFormExpanded}>
        {isAddFormExpanded ? 'Cancel' : 'Add new'}
      </button>
    {/if}
  </div>

  {#if showingCustom && hasServer && isAddFormExpanded}
    <AddSequenceForm
      onSubmit={async (text) => { await onAddCustomSequence(text); isAddFormExpanded = false; }}
      onCancel={() => isAddFormExpanded = false}
    />
  {/if}

  <!-- Sequences list -->
  <div class="sequences-list">
    {#if sortedSequences.length === 0}
      <div class="empty">No sequences to display</div>
    {:else}
      {#each sortedSequences as sequence, idx (`${sequence.interval || 'c'}-${sequence.sequence_id}-${idx}`)}
        <Example
          {sequence}
          {reductionMode}
          {transpose}
          {globalMaxActivation}
          {layer}
          {head}
          {onAttributionComplete}
          onDelete={showingCustom && hasServer ? onDeleteCustomSequence : null}
          {umapAvailable}
          {hasServer}
          {onUmapProjection}
        />
      {/each}
    {/if}
  </div>
</div>

<style>
  .sequences-tab {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }

  .controls-bar {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 10px 20px;
    background: #f5f5f5;
    border-bottom: 1px solid #e0e0e0;
    flex-shrink: 0;
  }

  .control-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .control-group label {
    font-size: 12px;
    color: #666;
    font-weight: 500;
  }

  .control-group select {
    padding: 4px 8px;
    font-size: 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
  }

  .add-button {
    margin-left: auto;
    background: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
  }

  .add-button:hover {
    background: #1976D2;
  }

  .reduction-hint {
    font-size: 11px;
    color: #888;
    font-style: italic;
  }

  .sequences-list {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    min-height: 0;
  }

  .empty {
    color: #666;
    text-align: center;
    padding: 20px;
  }
</style>
