// [Input] Vite mode env, React plugin, and public site URL build configuration.
// [Output] Build the SPA at the frontend origin root with SEO HTML placeholders resolved.
// [Pos] frontend build configuration
// [Sync] 2026-06-14: add Codex SEO public URL replacement for canonical, OG, and JSON-LD metadata.
// [Sync] 2026-06-15: remove /ink-and-memory/ deployment prefix; serve app at root.
// [Sync] 2026-06-23: proxy local auth/OAuth API routes to the FastAPI auth
//                    center during Vite dev while preserving the SPA Device
//                    Flow verification route.
// [Sync] 2026-07-20: upgrade to Vite 8 (rolldown/Rust bundler) so production
//                    builds fit 1G Docker build hosts — measured ~605MB peak RSS
//                    with a 512MB heap vs ~1.25GB RSS / 1024MB heap minimum on
//                    Vite 7+Rollup; disable gzip size reporting and sourcemaps,
//                    and split heavy static vendor chunks (react/tiptap/markdown/
//                    ai-sdk) while keeping mermaid and its d3/dagre/katex graph
//                    out of static chunks so MermaidBlock stays lazily loaded.
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const BASE_PATH = '/'
const DEFAULT_PUBLIC_SITE_URL = 'http://localhost:5173/'

function withTrailingSlash(value: string): string {
  return value.endsWith('/') ? value : `${value}/`
}

function joinSeoUrl(baseUrl: string, path: string): string {
  const cleanPath = path.replace(/^\/+/, '')
  return `${withTrailingSlash(baseUrl)}${cleanPath}`
}

function escapeHtmlAttribute(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function seoHtmlReplacementPlugin(publicSiteUrl: string): Plugin {
  const siteUrl = withTrailingSlash(publicSiteUrl.trim() || DEFAULT_PUBLIC_SITE_URL)
  const imageUrl = joinSeoUrl(siteUrl, 'login-banner.jpg')
  const replacements: Record<string, string> = {
    '%SEO_PUBLIC_SITE_URL%': escapeHtmlAttribute(siteUrl),
    '%SEO_PUBLIC_IMAGE_URL%': escapeHtmlAttribute(imageUrl),
    '%SEO_PUBLIC_SITE_URL_JSON%': JSON.stringify(siteUrl),
    '%SEO_PUBLIC_IMAGE_URL_JSON%': JSON.stringify(imageUrl),
  }

  return {
    name: 'ink-seo-html-replacements',
    transformIndexHtml(html) {
      let transformed = html
      for (const [token, replacement] of Object.entries(replacements)) {
        transformed = transformed.replaceAll(token, replacement)
      }
      return transformed
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const publicSiteUrl = env.VITE_PUBLIC_SITE_URL || DEFAULT_PUBLIC_SITE_URL

  return {
    plugins: [react(), seoHtmlReplacementPlugin(publicSiteUrl)],
    base: BASE_PATH,
    build: {
      // Low-memory profile: the builder stage runs on hosts with ~1G RAM.
      // Skip gzip-size reporting and sourcemaps to cut the output-phase peak.
      sourcemap: false,
      reportCompressedSize: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return
            // mermaid is dynamically imported by MermaidBlock; never hoist it
            // (or anything only reachable through it) into a static chunk.
            if (id.includes('/mermaid/') || id.includes('/@mermaid-js/')) return
            if (id.includes('/d3-') || id.includes('/dagre') || id.includes('/katex')) return
            if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')
              || id.includes('/react-i18next/') || id.includes('/i18next/')) {
              return 'vendor-react'
            }
            if (id.includes('/@tiptap/') || id.includes('/prosemirror-')) {
              return 'vendor-editor'
            }
            if (id.includes('/react-markdown/') || id.includes('/remark-') || id.includes('/rehype-')
              || id.includes('/micromark') || id.includes('/mdast-') || id.includes('/hast-')
              || id.includes('/highlight.js') || id.includes('/lowlight') || id.includes('/unist-')
              || id.includes('/unified/') || id.includes('/vfile') || id.includes('/decode-named')
              || id.includes('/devlop') || id.includes('/estree-') || id.includes('/comma-separated')
              || id.includes('/property-information') || id.includes('/space-separated')
              || id.includes('/html-url-attributes') || id.includes('/trim-lines')
              || id.includes('/markdown-table') || id.includes('/ccount') || id.includes('/zwitch')
              || id.includes('/bail') || id.includes('/trough') || id.includes('/extend')
              || id.includes('/is-plain-obj') || id.includes('/longest-streak')
              || id.includes('/stringify-entities') || id.includes('/character-entities')) {
              return 'vendor-markdown'
            }
            if (id.includes('/@ai-sdk/') || id.includes('/ai/') || id.includes('/zod/')) {
              return 'vendor-ai'
            }
          },
        },
      },
    },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8765',
          changeOrigin: true,
        },
        '/auth': {
          target: 'http://localhost:8765',
          changeOrigin: true,
        },
        '/oauth/device/verify': {
          target: 'http://localhost:8765',
          changeOrigin: true,
          bypass(req) {
            if (req.method === 'GET' && req.headers.accept?.includes('text/html')) {
              return '/index.html'
            }
          },
        },
        '/oauth': {
          target: 'http://localhost:8765',
          changeOrigin: true,
        },
        '/polycli': {
          target: 'http://localhost:8765',
          changeOrigin: true,
        }
      }
    }
  }
})
