// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Token rendering utilities.
 */

/**
 * Map of invisible characters to visible representations.
 */
const visibleCharacterFor = {
  '\u0000': '␀',
  '\u0001': '␁',
  '\u0002': '␂',
  '\u0003': '␃',
  '\u0004': '␄',
  '\u0005': '␅',
  '\u0006': '␆',
  '\u0007': '␇',
  '\u0008': '␈',
  '\u0009': '↹',  // tab
  '\u000A': '⏎',  // newline
  '\u000B': '␋',
  '\u000C': '␌',
  '\u000D': '␍',  // carriage return
  '\u000E': '␎',
  '\u000F': '␏',
}

/**
 * Render a string with visible representations of invisible characters.
 *
 * @param {string} s - Input string (e.g., a token)
 * @returns {string} String with invisible chars replaced
 */
export function renderStringVisibly(s) {
  if (!s) return ''
  return Array.from(s)
    .map(c => visibleCharacterFor[c] || c)
    .join('')
}

/**
 * Sanitize a token for display.
 * Replaces problematic Unicode with regular spaces, then renders visibly.
 *
 * @param {string} s - Input token string
 * @returns {string} Sanitized and visible string
 */
export function sanitizeToken(s) {
  if (s == null) return ''
  if (typeof s !== 'string') s = String(s)
  const sanitized = s
    .replace(/\u2028/g, ' ')  // LINE SEPARATOR
    .replace(/\u205f/g, ' ')  // MEDIUM MATHEMATICAL SPACE
  return renderStringVisibly(sanitized)
}

/**
 * Render a string visibly but preserve actual newlines for line breaks.
 *
 * @param {string} s - Input string
 * @returns {string} String with invisible chars replaced, newlines preserved
 */
export function renderStringVisiblyWithNewline(s) {
  if (!s) return ''
  return Array.from(s)
    .map(c => c === '\n' ? '⏎\n' : (visibleCharacterFor[c] || c))
    .join('')
}
