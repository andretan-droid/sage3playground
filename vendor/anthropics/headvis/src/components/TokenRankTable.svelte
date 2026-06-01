<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  let {
    items = [],
    maxRows = 30,
  } = $props()

  function renderToken(token) {
    if (!token) return ''
    return token
      .replace(/\n/g, '⏎')
      .replace(/\t/g, '↹')
      .replace(/\r/g, '↵')
  }

  function formatWeight(w) {
    if (w >= 100) return w.toFixed(0)
    if (w >= 10) return w.toFixed(1)
    return w.toFixed(2)
  }
</script>

<div class="table-scroll">
  <table>
    <thead><tr><th class="rank-col">#</th><th>Token</th><th class="numeric">Weight</th></tr></thead>
    <tbody>
      {#each items.slice(0, maxRows) as item, i}
        <tr>
          <td class="rank-cell">{i + 1}</td>
          <td class="token-cell">{renderToken(item.token)}</td>
          <td class="weight-cell">{formatWeight(item.weight)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .table-scroll {
    max-height: 500px;
    overflow-y: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    position: sticky;
    top: 0;
    background: white;
  }

  th {
    padding: 4px 12px;
    font-size: 10px;
    font-weight: 500;
    color: #999;
    text-align: left;
    border-bottom: 1px solid #eee;
  }

  th.numeric {
    text-align: right;
  }

  tbody tr:not(:last-child) td {
    border-bottom: 1px solid #f5f5f5;
  }

  .rank-col {
    width: 28px;
    text-align: right;
  }

  .rank-cell {
    font-family: monospace;
    font-size: 11px;
    padding: 3px 8px 3px 4px;
    text-align: right;
    color: #aaa;
  }

  .token-cell {
    font-family: monospace;
    font-size: 12px;
    padding: 3px 12px;
    white-space: pre;
    color: #333;
  }

  .weight-cell {
    font-family: monospace;
    font-size: 12px;
    padding: 3px 12px;
    text-align: right;
    color: #666;
  }
</style>
