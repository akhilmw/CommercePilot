const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ?? `Request failed with status ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

export const api = {
  listProducts: () => request("/api/products"),
  listProductRuns: (sku, limit = 20) =>
    request(`/api/products/${sku}/runs?limit=${limit}`),
  getTimeline: (runId) => request(`/api/runs/${runId}/timeline`),
  listApprovals: (status = "pending") =>
    request(`/api/approvals?status=${status}`),
  getMarket: (sku) => request(`/api/products/${sku}/market`),
  createRun: (body) =>
    request("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  decideApproval: (runId, approvalId, body) =>
    request(`/api/runs/${runId}/approvals/${approvalId}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createMarketSnapshot: (sku, body) =>
    request(`/api/products/${sku}/market/snapshots`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
