const services = [
  {
    id: "frontend",
    name: "Frontend",
    baseUrl: "http://localhost:8080",
    healthPath: "/health",
    role: "Service dashboard and static web UI",
  },
  {
    id: "scoring",
    name: "Scoring",
    baseUrl: "http://localhost:8000",
    healthPath: "/health",
    role: "Manual scoring model and ticker scoring",
  },
  {
    id: "batch",
    name: "Batch",
    baseUrl: "http://localhost:8001",
    healthPath: "/health",
    role: "Batch scoring execution",
  },
  {
    id: "portfolio",
    name: "Portfolio",
    baseUrl: "http://localhost:8003",
    healthPath: "/health",
    role: "Capital allocation and stop-loss levels",
  },
  {
    id: "risk",
    name: "Risk",
    baseUrl: "http://localhost:8004",
    healthPath: "/health",
    role: "Portfolio heat, profit lock, and macro checks",
  },
  {
    id: "screening",
    name: "Screening",
    baseUrl: "http://localhost:8005",
    healthPath: "/health",
    role: "Candidate screening and sector ranking",
  },
  {
    id: "notification",
    name: "Notification",
    baseUrl: "http://localhost:8006",
    healthPath: "/health",
    role: "Email and SMS notification intake",
  },
];

const endpointActions = [
  {
    serviceId: "scoring",
    title: "Scoring Model",
    method: "GET",
    path: "/v1/scoring-model",
    description: "Load the active scoring model configuration.",
  },
  {
    serviceId: "portfolio",
    title: "Allocate Portfolio",
    method: "POST",
    path: "/v1/portfolio/allocate",
    description: "Allocate capital across sample ranked candidates.",
    body: {
      capital: 100000,
      max_positions: 3,
      max_position_pct: 35,
      default_stop_loss_pct: 8,
      candidates: [
        { ticker: "MSFT", total_score: 91, price: 425 },
        { ticker: "NVDA", total_score: 88, price: 120 },
        { ticker: "AAPL", total_score: 82, price: 190 },
      ],
    },
  },
  {
    serviceId: "risk",
    title: "Evaluate Risk",
    method: "POST",
    path: "/v1/risk/evaluate",
    description: "Check portfolio heat, profit locks, and macro flags.",
    body: {
      capital: 100000,
      max_portfolio_heat_pct: 12,
      profit_lock_threshold_pct: 15,
      macro_flags: { fed_rate: "clear", earnings_season: "elevated" },
      positions: [
        { ticker: "MSFT", quantity: 20, entry_price: 360, current_price: 425, stop_loss_price: 390 },
        { ticker: "NVDA", quantity: 100, entry_price: 105, current_price: 120, stop_loss_price: 110 },
      ],
    },
  },
  {
    serviceId: "risk",
    title: "Week Rule",
    method: "POST",
    path: "/v1/risk/week-rule",
    description: "Return the risk rule for a holding period.",
    body: { holding_days: 18 },
  },
  {
    serviceId: "screening",
    title: "Screen Candidates",
    method: "POST",
    path: "/v1/screen",
    description: "Screen sample candidates by growth and quality.",
    body: {
      min_eps_growth_yoy: 5,
      min_revenue_growth_yoy: 0,
      min_score: 8,
      candidates: [
        {
          ticker: "MSFT",
          sector: "Technology",
          metrics: {
            growth_quality: { eps_growth_yoy: 14, revenue_growth_yoy: 11 },
            profitability: { operating_margin: 22, roic: 18 },
            financial_health: { debt_to_equity: 0.4 },
          },
        },
        {
          ticker: "XYZ",
          sector: "Industrials",
          metrics: {
            growth_quality: { eps_growth_yoy: -2, revenue_growth_yoy: 4 },
            profitability: { operating_margin: 9, roic: 7 },
            financial_health: { debt_to_equity: 1.8 },
          },
        },
      ],
    },
  },
  {
    serviceId: "notification",
    title: "Send Notification",
    method: "POST",
    path: "/v1/notifications/send",
    description: "Accept a sample email notification request.",
    body: {
      channel: "email",
      recipient: "analyst@example.com",
      subject: "Risk alert",
      message: "MSFT has triggered a profit-lock review.",
      severity: "info",
    },
  },
];

const serviceGrid = document.getElementById("service-grid");
const endpointGrid = document.getElementById("endpoint-grid");
const activeCount = document.getElementById("active-count");
const inactiveCount = document.getElementById("inactive-count");
const totalCount = document.getElementById("total-count");
const lastRefresh = document.getElementById("last-refresh");
const responseTitle = document.getElementById("response-title");
const responseOutput = document.getElementById("response-output");
const refreshButton = document.getElementById("refresh-button");

const state = Object.fromEntries(services.map((service) => [service.id, { status: "checking" }]));

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function serviceById(id) {
  return services.find((service) => service.id === id);
}

function renderServices() {
  serviceGrid.innerHTML = services
    .map((service) => {
      const current = state[service.id] || { status: "checking" };
      const statusText = current.status === "active" ? "Active" : current.status === "inactive" ? "Inactive" : "Checking";
      return `
        <article class="service-card">
          <div class="service-card__header">
            <div>
              <h3>${service.name}</h3>
              <p class="service-card__meta">${service.baseUrl}</p>
            </div>
            <span class="status-pill ${current.status}">${statusText}</span>
          </div>
          <p>${service.role}</p>
          <p class="service-card__meta">${current.detail || "No health response yet"}</p>
          <div class="service-card__actions">
            <button class="btn" data-open="${service.baseUrl}">Open</button>
            <button class="btn" data-health="${service.id}">Health</button>
          </div>
        </article>
      `;
    })
    .join("");

  const active = Object.values(state).filter((item) => item.status === "active").length;
  const inactive = Object.values(state).filter((item) => item.status === "inactive").length;
  activeCount.textContent = String(active);
  inactiveCount.textContent = String(inactive);
  totalCount.textContent = String(services.length);
}

function renderEndpoints() {
  endpointGrid.innerHTML = endpointActions
    .map((endpoint, index) => {
      const service = serviceById(endpoint.serviceId);
      return `
        <article class="endpoint-card">
          <span class="method">${endpoint.method}</span>
          <h3>${endpoint.title}</h3>
          <p class="endpoint-card__path">${service.baseUrl}${endpoint.path}</p>
          <p class="endpoint-card__description">${endpoint.description}</p>
          <div class="endpoint-card__actions">
            <button class="btn btn-primary" data-run="${index}">Run</button>
            <button class="btn" data-copy="${index}">Copy URL</button>
          </div>
        </article>
      `;
    })
    .join("");
}

async function checkHealth(service) {
  state[service.id] = { status: "checking", detail: "Checking health endpoint..." };
  renderServices();
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);
    const response = await fetch(`${service.baseUrl}${service.healthPath}`, { signal: controller.signal });
    clearTimeout(timeoutId);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    state[service.id] = {
      status: "active",
      detail: payload.service ? `${payload.service}: ${payload.status || "ok"}` : "Health check passed",
      payload,
    };
  } catch (error) {
    state[service.id] = {
      status: "inactive",
      detail: error.name === "AbortError" ? "Health check timed out" : error.message || "Health check failed",
    };
  }
  renderServices();
}

async function refreshAll() {
  refreshButton.disabled = true;
  await Promise.all(services.map((service) => checkHealth(service)));
  lastRefresh.textContent = `Last checked ${new Date().toLocaleTimeString()}`;
  refreshButton.disabled = false;
}

async function runEndpoint(endpoint) {
  const service = serviceById(endpoint.serviceId);
  const url = `${service.baseUrl}${endpoint.path}`;
  responseTitle.textContent = `${endpoint.method} ${url}`;
  responseOutput.textContent = "Request in progress...";

  try {
    const options =
      endpoint.method === "POST"
        ? {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(endpoint.body || {}),
          }
        : {};
    const response = await fetch(url, options);
    const payload = await response.json().catch(() => ({ status: response.status, body: "No JSON response" }));
    responseOutput.textContent = prettyJson(payload);
  } catch (error) {
    responseOutput.textContent = prettyJson({
      error: error.message || "Request failed",
      hint: "Check that the target service is running and reachable from this browser.",
    });
  }
}

document.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;

  const openUrl = target.getAttribute("data-open");
  if (openUrl) {
    window.open(openUrl, "_blank", "noopener,noreferrer");
    return;
  }

  const healthId = target.getAttribute("data-health");
  if (healthId) {
    const service = serviceById(healthId);
    if (service) await checkHealth(service);
    return;
  }

  const runIndex = target.getAttribute("data-run");
  if (runIndex !== null) {
    await runEndpoint(endpointActions[Number(runIndex)]);
    return;
  }

  const copyIndex = target.getAttribute("data-copy");
  if (copyIndex !== null) {
    const endpoint = endpointActions[Number(copyIndex)];
    const service = serviceById(endpoint.serviceId);
    await navigator.clipboard.writeText(`${service.baseUrl}${endpoint.path}`);
    responseTitle.textContent = "URL copied";
    responseOutput.textContent = `${service.baseUrl}${endpoint.path}`;
  }
});

refreshButton.addEventListener("click", refreshAll);

renderServices();
renderEndpoints();
refreshAll();
