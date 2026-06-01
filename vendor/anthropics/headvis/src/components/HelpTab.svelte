<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  let {
    metricDescriptions = {},
  } = $props()

  // Get sorted metrics with descriptions
  let metrics = $derived(
    Object.entries(metricDescriptions || {})
      .sort(([a], [b]) => a.localeCompare(b))
  )
</script>

<div class="help-tab">
  <div class="help-content">
    <section>
      <h3>Overview</h3>
      <p>
        HeadVis is an interactive visualization tool for exploring transformer attention heads.
        It displays attention patterns across example sequences organized by activation strength
        into quantile intervals, and allows computing feature-level attributions to understand
        <em>why</em> attention flows between specific token pairs.
      </p>
    </section>

    <section>
      <h3>Head Selection</h3>
      <p>
        The sidebar on the left shows a scatter plot of all attention heads, with each point
        representing one (layer, head) pair. Use the dropdowns to change which metrics are
        plotted on the X axis, Y axis, and color scale.
      </p>
      <ul>
        <li><strong>Click a point</strong> in the scatter plot to select that head and load its data.</li>
        <li><strong>Edit button</strong> (or double-click "Layer X Head Y") to open layer/head dropdowns for direct selection.</li>
        <li>The currently selected head is highlighted with an orange border in the scatter plot.</li>
        <li>The sidebar can be resized by dragging its right edge.</li>
      </ul>
    </section>

    <section>
      <h3>Keyboard Shortcuts</h3>

      <h4>Navigation</h4>
      <table>
        <tbody>
          <tr><td class="key">h / H</td><td>Next / Previous head (wraps around within current layer)</td></tr>
          <tr><td class="key">l / L</td><td>Next / Previous layer (wraps around)</td></tr>
          <tr><td class="key">[ / ]</td><td>Next / Previous interval (wraps around, includes Custom)</td></tr>
          <tr><td class="key">?</td><td>Open this Help tab</td></tr>
        </tbody>
      </table>

      <h4>View Controls</h4>
      <table>
        <tbody>
          <tr><td class="key">t / T</td><td>Toggle default transpose view</td></tr>
          <tr><td class="key">r / R</td><td>Toggle reduction mode (max / pairwise max)</td></tr>
          <tr><td class="key">m / M</td><td>Toggle between Sequences and Metrics tabs</td></tr>
          <tr><td class="key">Alt (hold)</td><td>Temporarily show transpose view while held</td></tr>
          <tr><td class="key">Escape</td><td>Cancel attribution mode</td></tr>
        </tbody>
      </table>

      <h4>Attribution Tab</h4>
      <table>
        <tbody>
          <tr><td class="key">&uarr; / &darr;</td><td>Navigate feature pairs in the attribution list</td></tr>
        </tbody>
      </table>
    </section>

    <section>
      <h3>View Modes</h3>

      <h4>Reduction Mode</h4>
      <ul>
        <li><strong>max</strong> - Token color = max activation over all Q/K pairs involving that position. Hover over any token to see its full attention pattern.</li>
        <li><strong>pairwise max</strong> - Shows only the single strongest Q&rarr;K attention pair (orange query, grey key with arrow).</li>
      </ul>

      <h4>Transpose View</h4>
      <ul>
        <li><strong>Default</strong> - Each token shows "how much attention does it give" (marginalize over keys).</li>
        <li><strong>Transpose</strong> - Each token shows "how much attention does it receive" (marginalize over queries).</li>
      </ul>
    </section>

    <section>
      <h3>QK and OV Attributions</h3>
      <p>
        Attributions decompose the attention between two tokens into <strong>SAE feature pairs</strong>.
        Each pair consists of a source feature and a target feature, with a score indicating
        how much that pair contributes to the attention pattern.
      </p>

      <h4>What are QK and OV?</h4>
      <ul>
        <li><strong>QK attribution</strong> answers: "Which features explain why this head attends from the <em>query</em> position to the <em>key</em> position?" It decomposes the query-key dot product into feature-level contributions.</li>
        <li><strong>OV attribution</strong> answers: "Which features explain how the <em>value</em> at the key position contributes to the <em>output</em> at the query position?" It decomposes the value-output pathway.</li>
      </ul>

      <h4>How to Compute an Attribution</h4>
      <ol>
        <li>On any sequence, click the <strong class="qk-label">QK</strong> or <strong class="ov-label">OV</strong> button in the sequence header.</li>
        <li>A pulsing indicator appears: "Click query token." Click any token to select the query position.</li>
        <li>The indicator updates to "Click key token." The attention pattern from the selected query is shown to help you pick an interesting key. Click a token to select the key position.</li>
        <li>The attribution is computed and the corresponding tab (QK or OV) opens automatically.</li>
      </ol>
      <p>Press <strong>Escape</strong> or click <strong>Cancel</strong> at any time to abort the selection.</p>

      <h4>Reading the Attribution Tab</h4>
      <ul>
        <li><strong>Top section</strong> - The source sequence with the selected Q and K tokens highlighted and labeled. Drag the bottom edge to resize.</li>
        <li><strong>Left panel</strong> - A ranked list of feature pairs by attribution score. Orange = positive contribution, blue = negative. Click a pair or use arrow keys to navigate. Drag the right edge to resize.</li>
        <li><strong>Right panel</strong> - Details for the selected pair: a diagram showing source feature &rarr; score &rarr; target feature, with example text snippets where each feature activates. Snippets are grouped by activation strength quantile.</li>
      </ul>
    </section>

    <section>
      <h3>Cache Indicators</h3>
      <p>
        Some attributions are precomputed and cached. Cached results load instantly without
        a server call. You can identify cached data in two ways:
      </p>
      <ul>
        <li><strong>Solid dark QK/OV buttons</strong> - When a sequence's QK or OV button is filled solid (dark blue or dark pink) instead of outlined, cached attribution data exists for at least one token pair in that sequence.</li>
        <li><strong>"cached" labels on tokens</strong> - During attribution mode, tokens with precomputed data for the current selection show a small "cached" label above them and an underline. These pairs will load instantly.</li>
      </ul>
    </section>

    <section>
      <h3>Custom Sequences</h3>
      <p>
        When a server is configured, you can run the attention computation on your own text
        rather than only viewing the pre-computed examples.
      </p>
      <ul>
        <li>Navigate to the <strong>"Custom"</strong> interval using the Interval dropdown or the <strong>[</strong> / <strong>]</strong> keys.</li>
        <li>Click <strong>"Add new"</strong> to open the input form. Enter or paste your text (max 256 tokens) and press <strong>Enter</strong> or click <strong>Add</strong>.</li>
        <li>The sequence will be tokenized and processed by the server, then displayed with the same attention patterns as the pre-computed examples.</li>
        <li>To delete a custom sequence, click the <strong class="delete-label">x</strong> button in its header.</li>
        <li>Press <strong>Escape</strong> to cancel and close the input form.</li>
      </ul>
    </section>

    <section>
      <h3>Visual Indicators</h3>
      <ul>
        <li><strong>Orange tokens</strong> - Higher attention activation (white-to-orange scale, normalized by head maximum).</li>
        <li><strong>Grey token with arrow (&darr;)</strong> - The associated key token in pairwise max mode.</li>
        <li><strong>Hover highlighting</strong> - In max mode, hover a token to see its full attention pattern across all positions.</li>
        <li><strong>Blue Q / K labels</strong> - Selected query/key tokens in QK attribution mode.</li>
        <li><strong>Pink Q / K labels</strong> - Selected query/key tokens in OV attribution mode.</li>
        <li><strong>Colorbar</strong> - The activation color scale (0 to 1) shown in the top-right of the panel header.</li>
      </ul>
    </section>

    <section>
      <h3>Metrics Tab</h3>
      <p>
        Press <strong>M</strong> or click the Metrics tab to view statistics for the selected head:
      </p>
      <ul>
        <li><strong>Histograms</strong> - Distribution of max activations and other configured metrics.</li>
        <li><strong>Custom plots</strong> - Additional visualizations defined in the data configuration.</li>
        <li><strong>Custom tables</strong> - Tabular data (e.g., top activating tokens) with numeric columns right-aligned.</li>
        <li><strong>Statistics</strong> - Key-value metrics for the current head (mean activation, sparsity, etc.).</li>
        <li><strong>Head metrics</strong> - The values plotted in the scatter plot for this head.</li>
      </ul>
    </section>

    <section>
      <h3>UMAP Tab</h3>
      <p>
        3D/2D scatter plots of QKOV embeddings per head. Available when the selected
        head has pre-computed UMAP data (indicated by the tab becoming clickable).
      </p>
      <ul>
        <li><strong>Hover</strong> over a point to see the corresponding sequence with Q and K tokens highlighted.</li>
        <li><strong>Lasso select</strong> to group points into named clusters for labeling.</li>
        <li><strong>Sidebar</strong> controls projection mode (UMAP/PCA), visible panels (O/V/Q/K), and color mode (rank/clusters).</li>
      </ul>
    </section>

    {#if metrics.length > 0}
      <section class="metrics-section">
        <h3>Metric Descriptions</h3>
        <div class="metrics-list">
          {#each metrics as [name, description]}
            <div class="metric-item">
              <dt>{name}</dt>
              <dd>{description}</dd>
            </div>
          {/each}
        </div>
      </section>
    {/if}
  </div>
</div>

<style>
  .help-tab {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
  }

  .help-content {
    max-width: 700px;
  }

  section {
    margin-bottom: 24px;
  }

  section:last-child {
    margin-bottom: 0;
  }

  h3 {
    margin: 0 0 12px 0;
    font-size: 16px;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 8px;
  }

  h4 {
    margin: 16px 0 8px 0;
    font-size: 13px;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  p {
    margin: 0 0 12px 0;
    color: #444;
    line-height: 1.5;
  }

  ul, ol {
    margin: 0;
    padding-left: 20px;
    color: #444;
    line-height: 1.8;
  }

  ol {
    line-height: 1.6;
  }

  ol li {
    margin-bottom: 4px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  td {
    padding: 6px 8px;
    border-bottom: 1px solid #f0f0f0;
  }

  td.key {
    font-family: monospace;
    font-size: 12px;
    background: #f5f5f5;
    width: 100px;
    font-weight: 500;
  }

  .qk-label {
    color: #1565c0;
  }

  .ov-label {
    color: #c2185b;
  }

  .delete-label {
    color: #d32f2f;
  }

  .metrics-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .metric-item {
    border-left: 3px solid #ddd;
    padding-left: 12px;
  }

  .metric-item dt {
    font-family: monospace;
    font-size: 13px;
    font-weight: 600;
    color: #333;
    margin-bottom: 4px;
  }

  .metric-item dd {
    margin: 0;
    font-size: 13px;
    color: #555;
    line-height: 1.5;
  }
</style>
