<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import FeatureSnippets from './FeatureSnippets.svelte'

  let {
    pair = null,
    sourceLabel = 'Key',
    targetLabel = 'Query',
    nIntervals = 10,
  } = $props()

  // Format score for display
  function formatScore(score) {
    if (score == null || isNaN(score)) return ''
    const absScore = Math.abs(score)
    if (absScore === 0) return '0'
    if (absScore < 0.001) return score.toExponential(2)
    if (absScore < 1) return score.toFixed(4)
    return score.toFixed(2)
  }

  // Whether only one side of the pair is populated (marginal single-feature view)
  let isSingleFeature = $derived(pair?.singleFeatureSide != null)

  // Background color based on score
  let backgroundColor = $derived.by(() => {
    if (!pair?.attribution) return 'transparent'
    const score = pair.attribution
    const magnitude = Math.abs(score)
    const alpha = Math.min(magnitude * 0.5, 0.5)
    if (score >= 0) {
      return `rgba(255, 140, 0, ${alpha})`
    } else {
      return `rgba(100, 149, 237, ${alpha})`
    }
  })
</script>

{#if pair}
  <div class="feature-panel">
    {#if isSingleFeature}
      <!-- Single feature view (marginal mode, no interaction selected yet) -->
      {@const side = pair.singleFeatureSide}
      {@const desc = side === 'key' ? pair.key_description : pair.query_description}
      {@const snips = side === 'key' ? pair.key_snippets : pair.query_snippets}
      {@const label = side === 'key' ? sourceLabel : targetLabel}
      <div class="single-header">
        <div class="feature-node">
          <div class="feature-type">{label} Feature</div>
        </div>
        <div class="attribution-value marginal" style:background-color={backgroundColor}>
          marginal: {formatScore(pair.attribution)}
        </div>
      </div>
      <div class="single-content">
        <div class="snippets-section">
          <div class="description-text">{desc || 'No description available'}</div>
          {#if snips?.length > 0}
            <FeatureSnippets snippets={snips} {nIntervals} />
          {/if}
        </div>
      </div>
    {:else}
      <!-- Full pair view -->
      <div class="header-row">
        <div class="header-side">
          <div class="spacer"></div>
          <div class="feature-node">
            <div class="feature-type">{sourceLabel} Feature</div>
          </div>
          <div class="edge-line"></div>
        </div>
        <div class="attribution-center">
          <div class="attribution-value" style:background-color={backgroundColor}>
            {formatScore(pair.attribution)}
          </div>
        </div>
        <div class="header-side">
          <div class="edge-line"></div>
          <div class="feature-node">
            <div class="feature-type">{targetLabel} Feature</div>
          </div>
          <div class="spacer"></div>
        </div>
      </div>

      <div class="content-row">
        <div class="feature-column">
          <div class="snippets-section">
            <div class="description-text">{pair.key_description || 'No description available'}</div>
            {#if pair.key_snippets?.length > 0}
              <FeatureSnippets snippets={pair.key_snippets} {nIntervals} />
            {/if}
          </div>
        </div>

        <div class="feature-column">
          <div class="snippets-section">
            <div class="description-text">{pair.query_description || 'No description available'}</div>
            {#if pair.query_snippets?.length > 0}
              <FeatureSnippets snippets={pair.query_snippets} {nIntervals} />
            {/if}
          </div>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .feature-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 20px;
    background: #fafafa;
    overflow-y: auto;
  }

  .header-row {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    padding: 8px 0;
    flex-shrink: 0;
  }

  .header-side {
    flex: 1;
    display: flex;
    align-items: center;
  }

  .spacer {
    flex: 1;
  }

  .feature-node {
    padding: 8px 16px;
    border-radius: 4px;
    background: white;
    border: 1px solid #ccc;
    text-align: center;
  }

  .feature-type {
    font-size: 11px;
    font-weight: 600;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .edge-line {
    flex: 1;
    height: 2px;
    background: #ccc;
  }

  .attribution-center {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .attribution-value {
    padding: 8px 16px;
    border-radius: 4px;
    font-family: monospace;
    font-weight: 600;
    font-size: 14px;
    color: #000;
    white-space: nowrap;
  }

  .content-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    flex: 1;
    min-height: 0;
  }

  .feature-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
    overflow-y: auto;
  }

  .description-text {
    font-size: 13px;
    color: #333;
    line-height: 1.5;
    margin-bottom: 8px;
  }

  .snippets-section {
    background: white;
    border-radius: 4px;
    border: 1px solid #ddd;
    padding: 12px;
    flex: 1;
    min-height: 200px;
    overflow-y: auto;
  }

  .single-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    flex-shrink: 0;
  }

  .attribution-value.marginal {
    font-size: 12px;
    font-weight: 500;
  }

  .single-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }
</style>
