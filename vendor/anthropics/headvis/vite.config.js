// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
import path from 'path'
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [
    svelte({
      onwarn: (warning, handler) => {
        if (warning.code.includes("a11y")) return
        handler(warning)
      }
    })
  ],
  root: "src",
  resolve: {
    alias: {
      '$lib': path.resolve(__dirname, 'src/lib'),
    },
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  base: './',
  optimizeDeps: {
    include: ['d3', 'plotly.js-dist-min']
  },
  server: process.env.DATA_URL ? {
    proxy: {
      '/data': {
        target: process.env.DATA_URL,
        changeOrigin: true,
      }
    }
  } : undefined
})
