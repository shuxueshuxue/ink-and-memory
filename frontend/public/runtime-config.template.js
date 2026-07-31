// [Input] API_BASE_URL and WS_BASE_URL rendered by frontend/docker-entrypoint.sh.
// [Output] Browser runtime API config consumed before the Vite bundle starts.
// [Pos] frontend runtime config template
window.__INK_RUNTIME_CONFIG__ = {
  apiBaseUrl: '${API_BASE_URL}',
  wsBaseUrl: '${WS_BASE_URL}'
};
