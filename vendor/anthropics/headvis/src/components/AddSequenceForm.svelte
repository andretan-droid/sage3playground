<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  let {
    onSubmit = null,  // async (text) => void
    onCancel = null,  // () => void
  } = $props()

  let text = $state('')
  let submitting = $state(false)
  let error = $state(null)

  async function handleSubmit() {
    if (!text.trim() || !onSubmit) return
    submitting = true
    error = null
    try {
      await onSubmit(text.trim())
      text = ''
    } catch (e) {
      error = e.message
    } finally {
      submitting = false
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      text = ''
      error = null
      if (onCancel) onCancel()
    }
  }
</script>

<div class="add-form">
  <textarea
    bind:value={text}
    placeholder="Enter text (max 256 tokens)..."
    disabled={submitting}
    onkeydown={handleKeydown}
    rows="2"
  ></textarea>
  <button
    onclick={handleSubmit}
    disabled={submitting || !text.trim()}
  >
    {submitting ? 'Adding...' : 'Add'}
  </button>
  {#if error}
    <div class="error">{error}</div>
  {/if}
</div>

<style>
  .add-form {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 10px 20px;
    border-bottom: 1px solid #e0e0e0;
    background: #fafafa;
  }

  textarea {
    flex: 1;
    padding: 6px 8px;
    font-size: 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    resize: vertical;
    font-family: inherit;
    min-height: 32px;
  }

  textarea:disabled {
    opacity: 0.5;
  }

  button {
    padding: 6px 12px;
    font-size: 12px;
    border: 1px solid #1565c0;
    border-radius: 4px;
    background: #1565c0;
    color: white;
    cursor: pointer;
    white-space: nowrap;
  }

  button:hover:not(:disabled) {
    background: #0d47a1;
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .error {
    font-size: 11px;
    color: #c62828;
    padding: 2px 0;
  }
</style>
