import React, { startTransition, useEffect, useState } from "react";
import "./index.css";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const STORAGE_KEY = "signal-deck-api-base-url";
const THEME_KEY = "signal-deck-theme";

function createTemplate(ticker) {
  return {
    ticker,
    as_of_date: new Date().toISOString().slice(0, 10),
    metrics: {
      growth_quality: {
        eps_growth_yoy: null,
        revenue_growth_yoy: null,
        ocf_growth_yoy: null,
        ocf_to_net_income: null,
      },
      profitability: {
        operating_margin: null,
        net_profit_margin: null,
        roic: null,
        roe: null,
      },
      financial_health: {
        debt_to_equity: null,
        current_ratio: null,
        interest_coverage: null,
      },
      valuation_sanity: {
        pe_ratio: null,
        pe_ratio_industry_avg: null,
        peg_ratio: null,
        ev_ebitda: null,
      },
      monitoring: {
        relative_strength: {
          status: "",
          outperformance_percent: null,
        },
        earnings_vs_guidance: "",
        analyst_actions: {
          upgrades: null,
          downgrades: null,
        },
        volume_trend: "",
        gross_margin_trend: "",
        ocf_vs_net_income_trend: "",
        capex_percent_sales: null,
        customer_concentration_trend: "",
      },
      risk_exit_signals: {
        margin_compression_bps: null,
        ocf_less_than_net_income: false,
        analyst_sentiment_shift: "",
        guidance_change: "",
        sector_momentum: "",
        relative_underperformance_percent: null,
      },
    },
    metadata: {
      source: "frontend-manual-entry",
      analyst: "",
    },
  };
}

function scoreDecisionText(result, threshold) {
  if (!result) return "Awaiting score";
  if (Number(result.total_score) < Number(threshold)) return "Rejected for further analysis";
  return "Ready for further analysis";
}

function editorForTicker(ticker) {
  return JSON.stringify(createTemplate(ticker), null, 2);
}

function nextTickerAfterSave(sessionTickers, resultsByTicker, currentTicker) {
  const currentIndex = sessionTickers.indexOf(currentTicker);
  const remaining = sessionTickers.slice(currentIndex + 1).find((ticker) => !resultsByTicker[ticker]);
  return remaining || currentTicker;
}

// Custom Typewriter Loading Component
function TypewriterLoader({ text, onComplete }) {
  const [displayed, setDisplayed] = useState("");

  useEffect(() => {
    let i = 0;
    const timer = setInterval(() => {
      setDisplayed(text.slice(0, i + 1));
      i++;
      if (i >= text.length) {
        clearInterval(timer);
        if (onComplete) setTimeout(onComplete, 500);
      }
    }, 40);
    return () => clearInterval(timer);
  }, [text, onComplete]);

  return (
    <div className="loading-screen">
      <div className="typewriter">
        <span>{displayed}</span>
        <span className="cursor">█</span>
      </div>
    </div>
  );
}

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem(THEME_KEY) || "dark");
  const [appState, setAppState] = useState("booting"); // 'booting' | 'ready'
  const [step, setStep] = useState(1); // 1 = Setup, 2 = Workspace
  
  const [apiBaseUrl, setApiBaseUrl] = useState(() => localStorage.getItem(STORAGE_KEY) || DEFAULT_API_BASE_URL);
  const [model, setModel] = useState(null);
  const [modelError, setModelError] = useState("");
  const [statusMessage, setStatusMessage] = useState("System initialized");
  
  const [setupForm, setSetupForm] = useState({ count: "", tickersCsv: "" });
  const [sessionTickers, setSessionTickers] = useState([]);
  const [stockEditors, setStockEditors] = useState({});
  const [activeTicker, setActiveTicker] = useState("");
  const [resultsByTicker, setResultsByTicker] = useState({});
  const [savingTicker, setSavingTicker] = useState("");
  const [settingUp, setSettingUp] = useState(false);

  const threshold = model?.pass_threshold ?? 85;

  // Theme Sync
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, apiBaseUrl);
  }, [apiBaseUrl]);

  // Initial Model Load
  useEffect(() => {
    let active = true;
    async function loadModel() {
      setModelError("");
      try {
        // Enforce a minimum delay so the loading animation completes smoothly
        const [response] = await Promise.all([
          fetch(`${apiBaseUrl.replace(/\/$/, "")}/v1/scoring-model`).catch(() => null),
          new Promise(res => setTimeout(res, 1800)) 
        ]);

        if (!response || !response.ok) throw new Error("Unable to load the scoring model.");

        const payload = await response.json();
        if (!active) return;

        startTransition(() => {
          setModel(payload);
        });
      } catch (error) {
        if (!active) return;
        setModelError(error.message || "Unable to load the scoring model.");
      }
    }
    loadModel();
    return () => { active = false; };
  }, [apiBaseUrl]);

  const toggleTheme = () => setTheme(prev => prev === "dark" ? "light" : "dark");

  async function handleSetupSubmit(event) {
    event.preventDefault();
    setSettingUp(true);
    setModelError("");
    setStatusMessage("Registering tickers...");

    try {
      const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/v1/stocks/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          count: Number(setupForm.count || 0),
          tickers_csv: setupForm.tickersCsv,
        }),
      });

      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to register the ticker list.");

      const requestedTickers = payload.requested_tickers || [];
      startTransition(() => {
        setSessionTickers(requestedTickers);
        setStockEditors((prev) => {
          const next = {};
          requestedTickers.forEach((t) => next[t] = prev[t] || editorForTicker(t));
          return next;
        });
        setActiveTicker(requestedTickers[0] || "");
        setResultsByTicker({});
        setStatusMessage(`Saved ${requestedTickers.length} ticker(s)`);
        setStep(2); // Move to next step sequentially
      });
    } catch (error) {
      setModelError(error.message || "Unable to register the ticker list.");
      setStatusMessage("Ticker registration failed");
    } finally {
      setSettingUp(false);
    }
  }

  function updateActiveEditor(value) {
    if (!activeTicker) return;
    setStockEditors((prev) => ({ ...prev, [activeTicker]: value }));
  }

  function resetActiveEditor() {
    if (!activeTicker) return;
    startTransition(() => {
      setStockEditors((prev) => ({ ...prev, [activeTicker]: editorForTicker(activeTicker) }));
      setStatusMessage(`Reset ${activeTicker} template`);
    });
  }

  async function handleSaveAndScore() {
    if (!activeTicker) return;
    setSavingTicker(activeTicker);
    setModelError("");
    setStatusMessage(`Running score for ${activeTicker}...`);

    try {
      const parsedPayload = JSON.parse(stockEditors[activeTicker]);
      parsedPayload.ticker = activeTicker;

      const response = await fetch(`${apiBaseUrl.replace(/\/$/, "")}/v1/manual-inputs/save-and-score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsedPayload),
      });

      const payload = await response.json();
      if (!response.ok) {
        const details = Array.isArray(payload.details) ? payload.details.join(" | ") : payload.error;
        throw new Error(details || `Unable to score ${activeTicker}.`);
      }

      const nextActiveTicker = nextTickerAfterSave(
        sessionTickers,
        { ...resultsByTicker, [activeTicker]: payload },
        activeTicker,
      );
      
      startTransition(() => {
        setResultsByTicker((prev) => ({ ...prev, [activeTicker]: payload }));
        setStatusMessage(`${activeTicker} scored at ${Number(payload.total_score).toFixed(2)}`);
        setActiveTicker(nextActiveTicker);
      });
    } catch (error) {
      setModelError(error.message || `Unable to score ${activeTicker}.`);
      setStatusMessage(`Scoring failed for ${activeTicker}`);
    } finally {
      setSavingTicker("");
    }
  }

  if (appState === "booting") {
    return <TypewriterLoader text="Initializing Signal Deck Intake..." onComplete={() => setAppState("ready")} />;
  }

  const scoredCount = sessionTickers.filter((t) => resultsByTicker[t]).length;
  const activeResult = activeTicker ? resultsByTicker[activeTicker] : null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__brand">
          <div className="brand-dot"></div>
          <strong>Signal Deck</strong> Intake
        </div>
        <div className="topbar__actions">
          <span className="status-indicator">{statusMessage}</span>
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === "light" ? "🌙 Dark" : "☀️ Light"}
          </button>
        </div>
      </header>

      <main className="main-content">
        {step === 1 && (
          <section className="step-container slide-in">
            <div className="card setup-card">
              <div className="card__header">
                <span className="step-badge">Step 1</span>
                <h1>Configuration & Registration</h1>
                <p className="subtitle">Set your API endpoint and define the batch of stocks to process.</p>
              </div>

              <form className="form-grid" onSubmit={handleSetupSubmit}>
                <label className="field-group">
                  <span className="label">API Base URL</span>
                  <input
                    type="url"
                    value={apiBaseUrl}
                    onChange={(e) => setApiBaseUrl(e.target.value)}
                    required
                  />
                </label>

                <div className="row-group">
                  <label className="field-group">
                    <span className="label">Stock Count</span>
                    <input
                      type="number"
                      min="1"
                      value={setupForm.count}
                      onChange={(e) => setSetupForm({ ...setupForm, count: e.target.value })}
                      placeholder="e.g. 3"
                      required
                    />
                  </label>
                  <label className="field-group flex-fill">
                    <span className="label">Tickers (CSV)</span>
                    <input
                      type="text"
                      value={setupForm.tickersCsv}
                      onChange={(e) => setSetupForm({ ...setupForm, tickersCsv: e.target.value.toUpperCase() })}
                      placeholder="MSFT, MU, NVDA"
                      required
                    />
                  </label>
                </div>

                {modelError && <div className="alert-error">{modelError}</div>}

                <div className="form-actions">
                  <button type="submit" className="btn btn-primary" disabled={settingUp}>
                    {settingUp ? "Initializing Workspace..." : "Proceed to Workspace →"}
                  </button>
                </div>
              </form>
            </div>
          </section>
        )}

        {step === 2 && (
          <section className="workspace-grid slide-in">
            <div className="workspace-header">
              <button className="btn btn-ghost" onClick={() => setStep(1)}>
                ← Back to Config
              </button>
              <div className="workspace-stats">
                <div className="stat-pill">Threshold: <strong>{threshold}</strong></div>
                <div className="stat-pill">Scored: <strong>{scoredCount} / {sessionTickers.length}</strong></div>
              </div>
            </div>

            <div className="workspace-columns">
              <div className="card editor-card">
                <div className="card__header">
                  <span className="step-badge">Step 2</span>
                  <h2>Data Entry</h2>
                </div>

                <div className="ticker-tabs">
                  {sessionTickers.map((ticker) => (
                    <button
                      key={ticker}
                      className={`tab ${ticker === activeTicker ? "active" : ""} ${resultsByTicker[ticker] ? "completed" : ""}`}
                      onClick={() => setActiveTicker(ticker)}
                    >
                      {ticker} {resultsByTicker[ticker] && "✓"}
                    </button>
                  ))}
                </div>

                <div className="editor-controls">
                  <span className="file-path">Target: /inputs/manual_metrics/{activeTicker}.json</span>
                  <div className="btn-group">
                    <button className="btn btn-outline" onClick={resetActiveEditor}>Reset JSON</button>
                    <button
                      className="btn btn-primary"
                      onClick={handleSaveAndScore}
                      disabled={!activeTicker || savingTicker === activeTicker}
                    >
                      {savingTicker === activeTicker ? "Processing..." : "Save & Score"}
                    </button>
                  </div>
                </div>

                <textarea
                  className="code-editor"
                  value={activeTicker ? stockEditors[activeTicker] || "" : ""}
                  onChange={(e) => updateActiveEditor(e.target.value)}
                  spellCheck="false"
                />
              </div>

              <div className="card results-card">
                <div className="card__header">
                  <span className="step-badge">Step 3</span>
                  <h2>Analysis Results</h2>
                </div>

                {modelError && <div className="alert-error">{modelError}</div>}

                <div className="results-list">
                  {sessionTickers.map((ticker) => {
                    const result = resultsByTicker[ticker];
                    const score = result ? Number(result.total_score).toFixed(2) : "--";
                    const isRejected = result && Number(result.total_score) < Number(threshold);

                    return (
                      <div className={`result-item ${isRejected ? "rejected" : ""} ${!result ? "pending" : ""}`} key={ticker}>
                        <div className="result-main">
                          <h3>{ticker}</h3>
                          <span className="score-val">{score}</span>
                        </div>
                        <p className="decision">{scoreDecisionText(result, threshold)}</p>
                      </div>
                    );
                  })}
                </div>

                {activeResult && (
                  <div className="active-focus">
                    <h4>Current Focus: {activeResult.ticker}</h4>
                    <div className="focus-score">{Number(activeResult.total_score).toFixed(2)}</div>
                    <p>{scoreDecisionText(activeResult, threshold)}</p>
                  </div>
                )}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}