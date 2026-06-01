// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Global state stores.
 * Uses Svelte 5 runes for reactive state.
 */

// Server configuration loaded from data/server_config.json
// Contains server_url and opaque context (forwarded to server)
let serverConfig = $state(null)
let serverConfigLoading = $state(true)
let serverConfigError = $state(null)

/**
 * Load server configuration from data/server_config.json.
 * Call this once on app startup.
 */
export async function loadServerConfig() {
  serverConfigLoading = true
  serverConfigError = null
  try {
    const response = await fetch('./data/server_config.json')
    if (!response.ok) {
      // No config file or empty - that's fine, server is optional
      serverConfig = null
      return
    }
    const data = await response.json()
    // Empty object means no server configured
    if (Object.keys(data).length === 0) {
      serverConfig = null
    } else {
      serverConfig = data
    }
  } catch (e) {
    // Config file doesn't exist or is invalid - no server available
    serverConfig = null
  } finally {
    serverConfigLoading = false
  }
}

export const serverStore = {
  // Full server config object {server_url, context}
  get config() { return serverConfig },
  // Just the server URL for display (if needed)
  get url() { return serverConfig?.server_url || '' },
  // Check if server is configured
  get isConfigured() { return serverConfig?.server_url != null },
  // Loading state
  get loading() { return serverConfigLoading },
  // Error state
  get error() { return serverConfigError }
}

// Active attribution state - holds current attribution to display in QK/OV tabs
// { sequence, type, queryPos, keyPos }
let activeAttribution = $state(null)

export const attributionStore = {
  // Get the current active attribution
  get active() { return activeAttribution },

  // Check if an attribution is active
  get isActive() { return activeAttribution !== null },

  // Get the active type ('qk' or 'ov') or null
  get activeType() { return activeAttribution?.type || null },

  /**
   * Set active attribution and switch to the appropriate tab.
   * Called by Example when user finishes selecting tokens.
   * @param {Object} sequence - The full sequence object
   * @param {string} type - 'qk' or 'ov'
   * @param {number} queryPos - Query token position
   * @param {number} keyPos - Key token position
   */
  setAttribution(sequence, type, queryPos, keyPos) {
    activeAttribution = { sequence, type, queryPos, keyPos }
  },

  /**
   * Clear the active attribution (when closing the tab or resetting).
   */
  clearAttribution() {
    activeAttribution = null
  }
}
