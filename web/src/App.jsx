import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";

const ACTIVE_RUNS = new Set(["pending", "running", "awaiting_approval"]);
const NAV_ITEMS = [
  { id: "portfolio", label: "Products", icon: "grid" },
  { id: "workspace", label: "Agent runs", icon: "pulse" },
  { id: "market", label: "Market simulator", icon: "chart" },
];

function Icon({ name }) {
  const paths = {
    grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    pulse: "M4 12h4l2-6 4 12 2-6h4",
    chart: "M5 19V9m7 10V5m7 14v-7M3 19h18",
    refresh: "M20 7v5h-5M4 17v-5h5M6.1 8a7 7 0 0 1 11.7-2L20 9M4 15l2.2 3a7 7 0 0 0 11.7-2",
    play: "m9 7 8 5-8 5z",
    check: "m5 12 4 4L19 6",
    close: "m7 7 10 10M17 7 7 17",
    box: "m4 7 8-4 8 4-8 4zM4 7v10l8 4 8-4V7M12 11v10",
    clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v5l3 2",
  };
  return (
    <svg className="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d={paths[name]} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StatusBadge({ status }) {
  const label = (status ?? "not_started").replaceAll("_", " ");
  return <span className={`status-badge status-${status ?? "idle"}`}>{label}</span>;
}

function formatMoney(value, currency = "USD") {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(Number(value));
}

function formatDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortId(value) {
  return value ? value.slice(0, 8).toUpperCase() : "—";
}

function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <span className="empty-icon"><Icon name="box" /></span>
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}

function Stat({ label, value, detail, tone = "default" }) {
  return <article className={`stat-card stat-${tone}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function ProductPortfolio({ products, selected, onSelect, onRun, onOpenRuns, search, setSearch }) {
  const filtered = products.filter((product) =>
    `${product.name} ${product.sku} ${product.category}`.toLowerCase().includes(search.toLowerCase()),
  );
  const activeRuns = products.filter((item) => ACTIVE_RUNS.has(item.latest_run?.status)).length;
  const openApprovals = products.reduce((total, item) => total + item.pending_approval_count, 0);
  const reviews = products.reduce((total, item) => total + item.review_count, 0);

  return (
    <>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Portfolio intelligence</p>
          <h1>Products</h1>
          <p className="page-subtitle">Choose a product to inspect signals or start an agent run.</p>
        </div>
        <label className="search-box">
          <span className="sr-only">Search products</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product or SKU" />
        </label>
      </header>

      <section className="stats-grid" aria-label="Portfolio summary">
        <Stat label="Products monitored" value={products.length} detail="Active catalog records" />
        <Stat label="Runs in progress" value={activeRuns} detail="Across the portfolio" />
        <Stat label="Open approvals" value={openApprovals} detail="Human decisions required" tone={openApprovals ? "warning" : "default"} />
        <Stat label="Reviews indexed" value={reviews} detail="Available to Review Agent" />
      </section>

      <div className="portfolio-layout">
        <section className="panel table-panel">
          <div className="panel-heading"><div><h2>Product portfolio</h2><p>Select a row for details</p></div><span className="record-count">{filtered.length} records</span></div>
          <div className="table-scroll">
            <table>
              <thead><tr><th>Product</th><th>Price</th><th>Signals</th><th>Latest run</th></tr></thead>
              <tbody>
                {filtered.map((product) => (
                  <tr key={product.id} className={selected?.id === product.id ? "selected-row" : ""} onClick={() => onSelect(product)}>
                    <td><div className="product-cell"><span className="product-mark">{product.name.charAt(0)}</span><span><strong>{product.name}</strong><small>{product.sku} · {product.category}</small></span></div></td>
                    <td>{formatMoney(product.price, product.currency)}</td>
                    <td><strong>{product.review_count}</strong><small>{product.competitor_count} competitors</small></td>
                    <td><StatusBadge status={product.latest_run?.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel product-detail">
          {selected ? (
            <>
              <div className="panel-heading"><div><h2>Selected product</h2><p>Catalog version {selected.catalog_version}</p></div><StatusBadge status={selected.status} /></div>
              <div className="detail-hero"><span className="product-mark large">{selected.name.charAt(0)}</span><div><h3>{selected.name}</h3><p>{selected.sku}</p><strong>{formatMoney(selected.price, selected.currency)}</strong></div></div>
              <dl className="detail-list">
                <div><dt>Customer reviews</dt><dd>{selected.review_count}</dd></div>
                <div><dt>Mapped competitors</dt><dd>{selected.competitor_count}</dd></div>
                <div><dt>Pending approvals</dt><dd>{selected.pending_approval_count}</dd></div>
                <div><dt>Latest run</dt><dd>{selected.latest_run ? shortId(selected.latest_run.id) : "None"}</dd></div>
              </dl>
              <div className="detail-note"><strong>Independent workflow</strong><p>A new cycle analyzes only this SKU and preserves every decision in its own run history.</p></div>
              <button className="button primary full" onClick={() => onRun(selected)}><Icon name="play" />Run intelligence cycle</button>
              <button className="button secondary full" onClick={onOpenRuns}><Icon name="clock" />View run history</button>
            </>
          ) : <EmptyState title="Select a product" description="Choose a portfolio row to inspect its intelligence state." />}
        </aside>
      </div>
    </>
  );
}

function RunWorkspace({ product, runs, selectedRun, timeline, approvals, onSelectRun, onDecision, comment, setComment }) {
  const runApproval = approvals.find((approval) => approval.run_id === selectedRun?.id);
  return (
    <>
      <header className="page-heading">
        <div><p className="eyebrow">Governed orchestration</p><h1>Agent runs</h1><p className="page-subtitle">Inspect LangGraph execution and resolve human checkpoints.</p></div>
        {selectedRun && <StatusBadge status={selectedRun.status} />}
      </header>
      <div className="workspace-layout">
        <aside className="panel run-list">
          <div className="panel-heading"><div><h2>{product?.name ?? "Run history"}</h2><p>{product?.sku}</p></div></div>
          {runs.length ? runs.map((run) => (
            <button key={run.id} className={`run-list-item ${selectedRun?.id === run.id ? "active" : ""}`} onClick={() => onSelectRun(run)}>
              <span><strong>Run {shortId(run.id)}</strong><small>{formatDate(run.created_at)}</small></span><StatusBadge status={run.status} />
            </button>
          )) : <EmptyState title="No runs yet" description="Start an intelligence cycle from the product portfolio." />}
        </aside>

        <section className="workspace-main">
          {selectedRun ? (
            <>
              <section className="panel timeline-panel">
                <div className="panel-heading"><div><h2>Run timeline</h2><p>Durable workflow state · {shortId(selectedRun.thread_id)}</p></div><span className="record-count">{timeline?.events?.length ?? 0} events</span></div>
                <div className="timeline">
                  {(timeline?.events ?? []).map((event, index) => (
                    <div className={`timeline-event event-${event.status}`} key={event.id}>
                      <div className="timeline-track"><span>{event.status === "approved" || event.status === "completed" ? "✓" : index + 1}</span></div>
                      <div><strong>{event.title}</strong><p>{event.details?.comment || event.event_type.replaceAll("_", " ")}</p></div><time>{formatDate(event.occurred_at)}</time>
                    </div>
                  ))}
                </div>
              </section>

              {runApproval ? <ApprovalPanel approval={runApproval} comment={comment} setComment={setComment} onDecision={onDecision} /> : (
                <section className="panel completion-panel"><span className="completion-icon"><Icon name="check" /></span><div><h2>{selectedRun.status === "completed" ? "Cycle completed" : "No decision required"}</h2><p>{selectedRun.status === "completed" ? "All approved actions finished and the audit trail is complete." : "The worker is processing this run. This view refreshes automatically."}</p></div></section>
              )}
            </>
          ) : <section className="panel"><EmptyState title="Choose a run" description="Select a run from the history to inspect its lifecycle." /></section>}
        </section>
      </div>
    </>
  );
}

function ApprovalPanel({ approval, comment, setComment, onDecision }) {
  const comparison = approval.payload?.comparison;
  const preview = approval.payload?.preview;
  return (
    <section className="panel approval-panel">
      <div className="panel-heading"><div><p className="eyebrow">Human checkpoint</p><h2>{approval.approval_type.replaceAll("_", " ")}</h2></div><StatusBadge status="awaiting_approval" /></div>
      {comparison && <div className="diff-stack">{comparison.fields.filter((field) => field.changed).map((field) => <div className="diff-card" key={field.field}><strong>{field.label}</strong><div className="diff-grid"><div><span>Current</span><p>{renderValue(field.current_value)}</p></div><div className="proposed"><span>Proposed</span><p>{renderValue(field.proposed_value)}</p></div></div></div>)}</div>}
      {preview && <div className="campaign-preview"><h3>{preview.name}</h3><p>{preview.objective}</p><div className="channel-grid">{preview.assets.map((asset) => <article key={asset.channel}><span>{asset.channel.replaceAll("_", " ")}</span><strong>{asset.headline}</strong><p>{asset.body}</p></article>)}</div></div>}
      <label className="comment-field"><span>Approval comment</span><textarea value={comment} onChange={(event) => setComment(event.target.value)} rows="3" /></label>
      <div className="approval-actions"><button className="button danger" onClick={() => onDecision(approval, false)}><Icon name="close" />Reject</button><button className="button primary" onClick={() => onDecision(approval, true)}><Icon name="check" />Approve & resume</button></div>
    </section>
  );
}

function renderValue(value) {
  if (value == null) return "Not set";
  if (Array.isArray(value)) return value.map((item) => typeof item === "string" ? item : item.text ?? JSON.stringify(item)).join(" · ");
  return String(value);
}

function MarketSimulator({ product, market, onSubmit, submitting }) {
  const [competitorSku, setCompetitorSku] = useState("");
  const [price, setPrice] = useState("");
  const [promotion, setPromotion] = useState("");
  useEffect(() => {
    const first = market?.competitors?.[0];
    if (first && !competitorSku) {
      setCompetitorSku(first.competitor_sku);
      setPrice(first.current_price);
    }
  }, [market, competitorSku]);
  const selected = market?.competitors?.find((item) => item.competitor_sku === competitorSku);
  const submit = (event) => {
    event.preventDefault();
    onSubmit({ competitor_sku: competitorSku, price, promotion: promotion || null });
  };
  return (
    <>
      <header className="page-heading"><div><p className="eyebrow">Controlled demo environment</p><h1>Market simulator</h1><p className="page-subtitle">Publish a competitor observation and see how the next agent cycle reacts.</p></div><StatusBadge status={product?.status} /></header>
      <div className="market-layout">
        <section className="panel market-board">
          <div className="panel-heading"><div><h2>Competitive price position</h2><p>{product?.name} is currently {formatMoney(market?.our_price, market?.currency)}</p></div><span className="record-count">{market?.competitors?.length ?? 0} tracked</span></div>
          <div className="market-cards">
            {(market?.competitors ?? []).map((competitor) => (
              <article key={competitor.competitor_product_id} className={competitor.is_cheaper_than_ours ? "market-card threat" : "market-card"}>
                <div><span className="competitor-name">{competitor.competitor_name}</span><small>{competitor.competitor_product_name}</small></div>
                <strong>{formatMoney(competitor.current_price, competitor.currency)}</strong>
                <span className={`price-change change-${competitor.change_type}`}>{Number(competitor.change_percent) > 0 ? "+" : ""}{competitor.change_percent}%</span>
                <p>{competitor.promotion || "No active promotion"}</p>
                <time>Observed {formatDate(competitor.observed_at)}</time>
              </article>
            ))}
          </div>
        </section>
        <aside className="panel simulator-form-panel">
          <div className="panel-heading"><div><h2>New market observation</h2><p>Creates an immutable snapshot</p></div></div>
          <form onSubmit={submit} className="simulator-form">
            <label><span>Competitor product</span><select value={competitorSku} onChange={(event) => { setCompetitorSku(event.target.value); const next = market.competitors.find((item) => item.competitor_sku === event.target.value); if (next) setPrice(next.current_price); }}>{(market?.competitors ?? []).map((item) => <option key={item.competitor_sku} value={item.competitor_sku}>{item.competitor_name} · {item.competitor_product_name}</option>)}</select></label>
            <label><span>Observed price</span><div className="money-input"><span>$</span><input type="number" min="0" step="0.01" required value={price} onChange={(event) => setPrice(event.target.value)} /></div></label>
            <label><span>Promotion label</span><input value={promotion} onChange={(event) => setPromotion(event.target.value)} placeholder="e.g. 48-hour flash sale" /></label>
            {selected && <div className="simulation-impact"><span>Projected signal</span><strong>{Number(price) < Number(market.our_price) ? `${selected.competitor_name} would undercut us by ${formatMoney(Number(market.our_price) - Number(price))}` : `${product.name} remains the lower-priced option`}</strong></div>}
            <button className="button primary full" disabled={submitting || !competitorSku}>{submitting ? "Publishing snapshot…" : "Publish market snapshot"}</button>
          </form>
          <p className="form-footnote">This changes competitor evidence only. Start a new intelligence cycle afterward to invoke the agents.</p>
        </aside>
      </div>
    </>
  );
}

export default function App() {
  const [view, setView] = useState("portfolio");
  const [products, setProducts] = useState([]);
  const [selectedSku, setSelectedSku] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [market, setMarket] = useState(null);
  const [search, setSearch] = useState("");
  const [comment, setComment] = useState("Evidence and proposed action reviewed.");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);

  const selectedProduct = products.find((item) => item.sku === selectedSku) ?? products[0] ?? null;
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null;

  const loadPortfolio = useCallback(async () => {
    const data = await api.listProducts();
    setProducts(data);
    setSelectedSku((current) => current ?? data[0]?.sku ?? null);
    return data;
  }, []);

  const loadProductContext = useCallback(async (sku) => {
    if (!sku) return;
    const [runData, marketData, approvalData] = await Promise.all([
      api.listProductRuns(sku),
      api.getMarket(sku),
      api.listApprovals("pending"),
    ]);
    setRuns(runData);
    setSelectedRunId((current) => runData.some((run) => run.id === current) ? current : runData[0]?.id ?? null);
    setMarket(marketData);
    setApprovals(approvalData);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const data = await loadPortfolio();
      const sku = selectedSku ?? data[0]?.sku;
      if (sku) await loadProductContext(sku);
    } catch (error) {
      setNotice({ tone: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }, [loadPortfolio, loadProductContext, selectedSku]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (selectedSku) loadProductContext(selectedSku).catch((error) => setNotice({ tone: "error", text: error.message })); }, [selectedSku, loadProductContext]);
  useEffect(() => {
    if (!selectedRun?.id) { setTimeline(null); return; }
    api.getTimeline(selectedRun.id).then(setTimeline).catch((error) => setNotice({ tone: "error", text: error.message }));
  }, [selectedRun?.id, selectedRun?.updated_at]);
  useEffect(() => {
    if (!selectedRun || !ACTIVE_RUNS.has(selectedRun.status)) return undefined;
    const timer = setInterval(() => refresh(), 3000);
    return () => clearInterval(timer);
  }, [selectedRun, refresh]);

  const runCycle = async (product) => {
    setBusy(true);
    try {
      const run = await api.createRun({ product_sku: product.sku });
      setSelectedSku(product.sku);
      setSelectedRunId(run.id);
      setView("workspace");
      setNotice({ tone: "success", text: `Run ${shortId(run.id)} queued for ${product.name}.` });
      await refresh();
    } catch (error) { setNotice({ tone: "error", text: error.message }); } finally { setBusy(false); }
  };

  const decide = async (approval, approved) => {
    setBusy(true);
    try {
      await api.decideApproval(approval.run_id, approval.id, { approved, reviewer: "akhil", comment });
      setNotice({ tone: "success", text: approved ? "Approved. The workflow is queued to resume." : "Rejected. No governed action will execute." });
      await refresh();
    } catch (error) { setNotice({ tone: "error", text: error.message }); } finally { setBusy(false); }
  };

  const simulate = async (payload) => {
    if (!selectedProduct) return;
    setBusy(true);
    try {
      const result = await api.createMarketSnapshot(selectedProduct.sku, payload);
      setNotice({ tone: "success", text: `${result.competitor_name} recorded at ${formatMoney(result.current_price)} (${result.change_percent}%).` });
      setMarket(await api.getMarket(selectedProduct.sku));
    } catch (error) { setNotice({ tone: "error", text: error.message }); } finally { setBusy(false); }
  };

  const page = useMemo(() => {
    if (view === "workspace") return <RunWorkspace product={selectedProduct} runs={runs} selectedRun={selectedRun} timeline={timeline} approvals={approvals} onSelectRun={(run) => setSelectedRunId(run.id)} onDecision={decide} comment={comment} setComment={setComment} />;
    if (view === "market") return <MarketSimulator product={selectedProduct} market={market} onSubmit={simulate} submitting={busy} />;
    return <ProductPortfolio products={products} selected={selectedProduct} onSelect={(product) => setSelectedSku(product.sku)} onRun={runCycle} onOpenRuns={() => setView("workspace")} search={search} setSearch={setSearch} />;
  }, [view, products, selectedProduct, runs, selectedRun, timeline, approvals, comment, market, busy, search]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">C</span><span><strong>CommercePilot</strong><small>Agent operations</small></span></div>
        <nav><p>Workspace</p>{NAV_ITEMS.map((item) => <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}><Icon name={item.icon} /><span>{item.label}</span>{item.id === "workspace" && approvals.length > 0 && <b>{approvals.length}</b>}</button>)}</nav>
        <div className="governance-note"><span><Icon name="check" /></span><p><strong>Governed execution</strong>Price, catalog, and campaign actions require human approval.</p></div>
      </aside>
      <main className="main-content">
        <div className="topbar"><span>NovaCart / {NAV_ITEMS.find((item) => item.id === view)?.label}</span><div className="topbar-actions"><button className="icon-button" onClick={refresh} aria-label="Refresh data"><Icon name="refresh" /></button><span className="operator">AN</span></div></div>
        {notice && <div className={`notice notice-${notice.tone}`}><span>{notice.text}</span><button onClick={() => setNotice(null)} aria-label="Dismiss"><Icon name="close" /></button></div>}
        {loading ? <div className="loading-state"><span></span><p>Loading commerce intelligence…</p></div> : page}
      </main>
      {busy && <div className="busy-bar" aria-label="Request in progress" />}
    </div>
  );
}
