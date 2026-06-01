<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import Token from './Token.svelte'
  import { createSparse, getRowMax, getColMax } from '../lib/sparse.js'
  import { computeReduction } from '../lib/reductions.js'
  import { getAttentionColor } from '../lib/colors.js'

  let {
    sequence = null,
    reductionMode = 'pairwise_max',
    transpose = false,
    globalMaxActivation = 1.0,
    queryPos = null,
    keyPos = null,
    attributionType = null,  // 'qk' or 'ov' — for selection highlight colors
    fixedIdx = null,  // If set, show this token's attention pattern by default
  } = $props()

  // Create sparse tensor from sequence data
  let sparse = $derived(sequence ? createSparse(
    sequence.attention_indices,
    sequence.attention_values,
    sequence.seq_len
  ) : null)

  // Hovered token index for hover mode — falls back to fixedIdx when not hovering
  let hoveredIdx = $state(null)
  let effectiveIdx = $derived(hoveredIdx ?? fixedIdx)

  // Compute reduced activations based on mode
  let reduction = $derived(sparse ? computeReduction(sparse, reductionMode, effectiveIdx, transpose) : null)

  // Build tokens with colors
  let tokens = $derived(sequence ? sequence.tokens.map((text, i) => ({
    text,
    index: i,
    activation: reduction ? reduction.activations[i] : 0,
    color: reduction ? getAttentionColor(reduction.activations[i], globalMaxActivation) : 'transparent',
    isAssociated: reduction?.pairInfo?.keyIdx === i,
    isQuerySelected: i === queryPos,
    isKeySelected: i === keyPos,
  })) : [])

  function handleHover(idx) {
    if (reductionMode === 'max' || reductionMode === 'pairwise_max') {
      hoveredIdx = idx
    }
  }
</script>

{#if sequence}
  <div class="sequence-display">
    <div class="header">
      <span class="sequence-id">{sequence.sequence_id}</span>
      <span class="max-act">max: {sequence.max_activation.toFixed(3)}</span>
    </div>
    <div class="tokens" onmouseleave={() => hoveredIdx = null} role="presentation">
      {#each tokens as token (token.index)}
        <Token
          text={token.text}
          color={token.color}
          isAssociated={token.isAssociated}
          index={token.index}
          activation={token.activation}
          isQuerySelected={token.isQuerySelected}
          isKeySelected={token.isKeySelected}
          attributionType={attributionType}
          onHover={handleHover}
        />
      {/each}
    </div>
  </div>
{/if}

<style>
  .sequence-display {
    width: 100%;
  }

  .header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 10px;
    font-size: 11px;
    color: #666;
    border-bottom: 1px solid #e0e0e0;
  }

  .sequence-id {
    font-family: monospace;
    font-weight: 500;
    background: #e0e0e0;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
  }

  .max-act {
    font-family: monospace;
  }

  .tokens {
    display: flex;
    flex-wrap: wrap;
    padding: 6px 8px;
  }
</style>
