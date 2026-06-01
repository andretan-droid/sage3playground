// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Custom sequences API and static-fetch helpers.
 *
 * Two-mode protocol:
 * - Static mode: fetch from ./data/custom_sequences/L{layer}H{head}.json (no server needed)
 * - Server mode: POST to server for add/delete operations
 */
import { serverStore } from './stores.svelte.js'

/**
 * Load custom sequences for a head.
 * Always tries static fetch first (works without server).
 * @param {number} layer - Layer index
 * @param {number} head - Head index
 * @returns {Promise<Array>} Array of custom sequence objects
 */
export async function loadCustomSequences(layer, head) {
  const url = `./data/custom_sequences/L${layer}H${head}.json`
  try {
    const response = await fetch(url)
    if (!response.ok) return []
    const data = await response.json()
    return data.sequences || []
  } catch {
    return []
  }
}

/**
 * Add a custom sequence via server.
 * @param {number} layer - Layer index
 * @param {number} head - Head index
 * @param {string} text - The text to add
 * @returns {Promise<Object>} The new sequence data
 */
export async function addCustomSequence(layer, head, text) {
  const config = serverStore.config
  if (!config?.server_url) {
    throw new Error('No server configured')
  }

  const response = await fetch(`${config.server_url}/api/head_vis/public/add_custom_sequence/v0`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      layer,
      head,
      text,
      context: config.context || {},
    }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail || 'Failed to add sequence')
  }

  return await response.json()
}

/**
 * Delete a custom sequence via server.
 * @param {number} layer - Layer index
 * @param {number} head - Head index
 * @param {string} sequenceId - The sequence ID to delete (e.g., "cabc123")
 * @returns {Promise<Object>} Deletion result
 */
export async function deleteCustomSequence(layer, head, sequenceId) {
  const config = serverStore.config
  if (!config?.server_url) {
    throw new Error('No server configured')
  }

  const response = await fetch(`${config.server_url}/api/head_vis/public/delete_custom_sequence/v0`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      layer,
      head,
      sequence_id: sequenceId,
      context: config.context || {},
    }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail || 'Failed to delete sequence')
  }

  return await response.json()
}
