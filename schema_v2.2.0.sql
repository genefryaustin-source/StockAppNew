CREATE TABLE tenants (
	id VARCHAR NOT NULL, 
	name VARCHAR, 
	created_at DATETIME, is_active INTEGER DEFAULT 1, 
	PRIMARY KEY (id)
);
CREATE TABLE users (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR, 
	email VARCHAR, 
	role VARCHAR, 
	created_at DATETIME, password_hash TEXT, is_active INTEGER DEFAULT 1, 
	PRIMARY KEY (id)
);
CREATE TABLE fundamental_snapshots (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	asof DATETIME, 
	market_cap FLOAT, 
	revenue_ttm FLOAT, 
	net_income FLOAT, 
	ebitda FLOAT, 
	cash FLOAT, 
	total_debt FLOAT, 
	shares_outstanding FLOAT, 
	sector VARCHAR, 
	gross_margin FLOAT, 
	op_margin FLOAT, 
	fcf_margin FLOAT, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_fund_tenant_sym_asof ON fundamental_snapshots (tenant_id, symbol, asof);
CREATE INDEX ix_fundamental_snapshots_tenant_id ON fundamental_snapshots (tenant_id);
CREATE INDEX ix_fundamental_snapshots_asof ON fundamental_snapshots (asof);
CREATE INDEX ix_fundamental_snapshots_symbol ON fundamental_snapshots (symbol);
CREATE TABLE financial_periods (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	period_type VARCHAR NOT NULL, 
	period_end DATETIME NOT NULL, 
	fiscal_year FLOAT, 
	fiscal_period VARCHAR, 
	revenue FLOAT, 
	gross_profit FLOAT, 
	operating_income FLOAT, 
	net_income FLOAT, 
	eps_basic FLOAT, 
	eps_diluted FLOAT, 
	ebitda FLOAT, 
	operating_cash_flow FLOAT, 
	capex FLOAT, 
	free_cash_flow FLOAT, 
	cash FLOAT, 
	total_debt FLOAT, 
	created_at DATETIME, source TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_fin_period UNIQUE (tenant_id, symbol, period_type, period_end)
);
CREATE INDEX ix_financial_periods_tenant_id ON financial_periods (tenant_id);
CREATE INDEX ix_financial_periods_period_end ON financial_periods (period_end);
CREATE INDEX ix_financial_periods_symbol ON financial_periods (symbol);
CREATE INDEX ix_fin_period_lookup ON financial_periods (tenant_id, symbol, period_type, period_end);
CREATE INDEX ix_financial_periods_period_type ON financial_periods (period_type);
CREATE TABLE earnings_events (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	event_date DATETIME, 
	time_of_day VARCHAR, 
	eps_est FLOAT, 
	rev_est FLOAT, 
	created_at DATETIME, earnings_date DATETIME, eps_actual REAL, eps_estimate REAL, revenue_actual REAL, revenue_estimate REAL, source TEXT, rev_actual REAL, rev_estimate REAL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_earn_tenant_sym_date ON earnings_events (tenant_id, symbol, event_date);
CREATE INDEX ix_earnings_events_symbol ON earnings_events (symbol);
CREATE INDEX ix_earnings_events_event_date ON earnings_events (event_date);
CREATE INDEX ix_earnings_events_tenant_id ON earnings_events (tenant_id);
CREATE TABLE analytics_snapshots (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	asof DATETIME, 
	sector VARCHAR, 
	revenue_cagr_3y FLOAT, 
	gross_margin FLOAT, 
	op_margin FLOAT, 
	fcf_margin FLOAT, 
	pe_ttm FLOAT, 
	ps_ttm FLOAT, 
	ev_ebitda FLOAT, 
	trend VARCHAR, 
	rsi_14 FLOAT, 
	sma_50 FLOAT, 
	sma_200 FLOAT, 
	support FLOAT, 
	resistance FLOAT, 
	vol_20d FLOAT, 
	max_drawdown_1y FLOAT, 
	risk_score FLOAT, 
	rating VARCHAR, 
	rating_rationale TEXT, 
	quality_score FLOAT, 
	growth_score FLOAT, 
	value_score FLOAT, 
	momentum_score FLOAT, 
	composite_score FLOAT, 
	confidence_score FLOAT, operating_margin FLOAT, revenue_cagr FLOAT, latest_volume FLOAT, signal TEXT, signal_rationale TEXT, sentiment_score REAL, momentum REAL, value REAL, growth REAL, quality REAL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_analytics_snapshots_asof ON analytics_snapshots (asof);
CREATE INDEX ix_analytics_tenant_sym_asof ON analytics_snapshots (tenant_id, symbol, asof);
CREATE INDEX ix_analytics_snapshots_sector ON analytics_snapshots (sector);
CREATE INDEX ix_analytics_snapshots_tenant_id ON analytics_snapshots (tenant_id);
CREATE INDEX ix_analytics_tenant_sector_asof ON analytics_snapshots (tenant_id, sector, asof);
CREATE INDEX ix_analytics_snapshots_symbol ON analytics_snapshots (symbol);
CREATE TABLE alert_events (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	created_at DATETIME, 
	alert_type VARCHAR NOT NULL, 
	last_price FLOAT, 
	support FLOAT, 
	resistance FLOAT, 
	previous_rating VARCHAR, 
	new_rating VARCHAR, 
	title VARCHAR NOT NULL, 
	message TEXT NOT NULL, 
	acknowledged BOOLEAN, 
	acknowledged_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_alert_events_created_at ON alert_events (created_at);
CREATE INDEX ix_alert_events_alert_type ON alert_events (alert_type);
CREATE INDEX ix_alert_events_acknowledged ON alert_events (acknowledged);
CREATE INDEX ix_alert_tenant_sym_time ON alert_events (tenant_id, symbol, created_at);
CREATE INDEX ix_alert_tenant_ack ON alert_events (tenant_id, acknowledged);
CREATE INDEX ix_alert_events_tenant_id ON alert_events (tenant_id);
CREATE INDEX ix_alert_events_symbol ON alert_events (symbol);
CREATE TABLE universes (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	description TEXT, 
	created_by_user_id VARCHAR, 
	created_at DATETIME NOT NULL, updated_at TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_universe_tenant_name UNIQUE (tenant_id, name)
);
CREATE INDEX ix_universe_tenant_created ON universes (tenant_id, created_at);
CREATE INDEX ix_universes_tenant_id ON universes (tenant_id);
CREATE TABLE universe_analytics_cache (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	universe_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	analytics_snapshot_id VARCHAR, 
	analytics_asof DATETIME, 
	sector VARCHAR, 
	rating VARCHAR, 
	composite_score FLOAT, 
	confidence_score FLOAT, 
	quality FLOAT, 
	growth FLOAT, 
	value FLOAT, 
	momentum FLOAT, 
	risk FLOAT, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_uac_tenant_universe_symbol UNIQUE (tenant_id, universe_id, symbol)
);
CREATE INDEX ix_uac_tenant_universe ON universe_analytics_cache (tenant_id, universe_id);
CREATE INDEX ix_universe_analytics_cache_analytics_snapshot_id ON universe_analytics_cache (analytics_snapshot_id);
CREATE INDEX ix_uac_universe_rank ON universe_analytics_cache (tenant_id, universe_id, composite_score, confidence_score);
CREATE INDEX ix_universe_analytics_cache_analytics_asof ON universe_analytics_cache (analytics_asof);
CREATE INDEX ix_universe_analytics_cache_universe_id ON universe_analytics_cache (universe_id);
CREATE INDEX ix_universe_analytics_cache_updated_at ON universe_analytics_cache (updated_at);
CREATE INDEX ix_universe_analytics_cache_symbol ON universe_analytics_cache (symbol);
CREATE INDEX ix_universe_analytics_cache_tenant_id ON universe_analytics_cache (tenant_id);
CREATE TABLE jobs (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	job_type VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	universe_id VARCHAR, 
	symbol VARCHAR, 
	total INTEGER, 
	done INTEGER, 
	payload TEXT, 
	logs TEXT, 
	error TEXT, 
	created_at VARCHAR, 
	started_at VARCHAR, 
	finished_at VARCHAR, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_jobs_tenant_id ON jobs (tenant_id);
CREATE INDEX ix_jobs_universe_id ON jobs (universe_id);
CREATE INDEX ix_jobs_symbol ON jobs (symbol);
CREATE INDEX ix_jobs_job_type ON jobs (job_type);
CREATE INDEX ix_jobs_status ON jobs (status);
CREATE TABLE watchlists (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	created_at DATETIME, created_by_user_id TEXT, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_watchlists_tenant_id ON watchlists (tenant_id);
CREATE TABLE watchlist_items (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	watchlist_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(watchlist_id) REFERENCES watchlists (id)
);
CREATE INDEX ix_watchlist_items_symbol ON watchlist_items (symbol);
CREATE INDEX ix_watchlist_items_watchlist_id ON watchlist_items (watchlist_id);
CREATE INDEX ix_watchlist_items_tenant_id ON watchlist_items (tenant_id);
CREATE TABLE portfolios (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at DATETIME
, description TEXT, benchmark TEXT, base_currency TEXT NOT NULL DEFAULT 'USD', starting_cash REAL NOT NULL DEFAULT 100000.0, is_active INTEGER NOT NULL DEFAULT 1, updated_at DATETIME, owner_user_id TEXT);
CREATE TABLE portfolio_trades (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    trade_date DATETIME
);
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    portfolio TEXT,
    ticker TEXT,
    shares REAL,
    price REAL
);
CREATE TABLE market_data_cache (
	symbol VARCHAR NOT NULL, 
	latest_price FLOAT, 
	history_json TEXT, 
	updated_at DATETIME, 
	PRIMARY KEY (symbol)
);
CREATE INDEX idx_snapshot_rank
ON analytics_snapshots (
    tenant_id,
    composite_score,
    confidence_score,
    asof
);
CREATE TABLE discovered_strategies (
	id VARCHAR NOT NULL, 
	tenant_id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	factors VARCHAR, 
	holdings TEXT, 
	return_pct FLOAT, 
	spy_return FLOAT, 
	alpha FLOAT, 
	sharpe FLOAT, 
	max_drawdown FLOAT, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_strategy_tenant_name ON discovered_strategies (tenant_id, name);
CREATE INDEX ix_discovered_strategies_tenant_id ON discovered_strategies (tenant_id);
CREATE INDEX idx_analytics_symbol
ON analytics_snapshots(symbol);
CREATE INDEX idx_analytics_asof
ON analytics_snapshots(asof);
CREATE TABLE price_history (

    symbol TEXT NOT NULL,

    date DATE NOT NULL,

    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,

    PRIMARY KEY(symbol, date)

);
CREATE INDEX idx_price_symbol_date
ON price_history(symbol, date);
CREATE TABLE factor_store (
	tenant_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	updated_at DATETIME, 
	sector VARCHAR, 
	rating VARCHAR, 
	composite FLOAT, 
	confidence FLOAT, 
	quality FLOAT, 
	growth FLOAT, 
	value FLOAT, 
	momentum FLOAT, 
	risk FLOAT, 
	rsi FLOAT, 
	sma50 FLOAT, 
	sma200 FLOAT, 
	support FLOAT, 
	resistance FLOAT, 
	volatility FLOAT, 
	drawdown FLOAT, 
	trend VARCHAR, 
	revenue_cagr FLOAT, 
	gross_margin FLOAT, 
	op_margin FLOAT, 
	fcf_margin FLOAT, 
	pe FLOAT, 
	ps FLOAT, 
	ev_ebitda FLOAT, 
	PRIMARY KEY (tenant_id, symbol)
);
CREATE INDEX ix_factor_store_tenant_composite ON factor_store (tenant_id, composite);
CREATE INDEX ix_factor_store_composite ON factor_store (composite);
CREATE INDEX ix_factor_store_confidence ON factor_store (confidence);
CREATE INDEX ix_factor_store_updated_at ON factor_store (updated_at);
CREATE INDEX ix_factor_store_tenant_sector ON factor_store (tenant_id, sector);
CREATE INDEX ix_factor_store_sector ON factor_store (sector);
CREATE TABLE "universe_symbols"(symbol TEXT, tenant_id TEXT, universe_id TEXT);
CREATE UNIQUE INDEX idx_universe_symbol
ON universe_symbols(symbol);
CREATE TABLE universe_equities(symbol TEXT);
CREATE INDEX idx_universe_symbols_tenant
ON universe_symbols (tenant_id);
CREATE INDEX idx_universe_symbols_universe
ON universe_symbols (universe_id);
CREATE TABLE security_master (
    symbol TEXT PRIMARY KEY,
    exchange TEXT,
    is_etf INTEGER DEFAULT 0,
    sector TEXT,
    industry TEXT,
    source TEXT,
    updated_at TEXT
);
CREATE TABLE trade_orders (
	id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	portfolio_id INTEGER NOT NULL, 
	user_id INTEGER, 
	broker VARCHAR(50) NOT NULL, 
	broker_order_id VARCHAR(100), 
	symbol VARCHAR(20) NOT NULL, 
	side VARCHAR(10) NOT NULL, 
	order_type VARCHAR(20) NOT NULL, 
	tif VARCHAR(20) NOT NULL, 
	qty FLOAT NOT NULL, 
	limit_price FLOAT, 
	stop_price FLOAT, 
	status VARCHAR(30) NOT NULL, 
	submitted_at DATETIME, 
	filled_at DATETIME, 
	canceled_at DATETIME, 
	avg_fill_price FLOAT, 
	filled_qty FLOAT NOT NULL, 
	estimated_commission FLOAT NOT NULL, 
	actual_commission FLOAT NOT NULL, 
	estimated_slippage FLOAT NOT NULL, 
	actual_slippage FLOAT NOT NULL, 
	notes TEXT, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_trade_orders_portfolio_id ON trade_orders (portfolio_id);
CREATE INDEX ix_trade_orders_user_id ON trade_orders (user_id);
CREATE INDEX ix_trade_orders_broker_order_id ON trade_orders (broker_order_id);
CREATE INDEX ix_trade_orders_symbol ON trade_orders (symbol);
CREATE TABLE portfolio_daily_pnl (
	id INTEGER NOT NULL, 
	portfolio_id INTEGER NOT NULL, 
	as_of_date DATE NOT NULL, 
	gross_realized_pnl FLOAT NOT NULL, 
	gross_unrealized_pnl FLOAT NOT NULL, 
	commissions FLOAT NOT NULL, 
	slippage FLOAT NOT NULL, 
	net_pnl FLOAT NOT NULL, 
	cash FLOAT NOT NULL, 
	equity FLOAT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_portfolio_daily_pnl_portfolio_id ON portfolio_daily_pnl (portfolio_id);
CREATE INDEX ix_portfolio_daily_pnl_as_of_date ON portfolio_daily_pnl (as_of_date);
CREATE TABLE trade_fills (
	id INTEGER NOT NULL, 
	order_id INTEGER NOT NULL, 
	broker_fill_id VARCHAR(100), 
	filled_at DATETIME NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	side VARCHAR(10) NOT NULL, 
	qty FLOAT NOT NULL, 
	price FLOAT NOT NULL, 
	commission FLOAT NOT NULL, 
	slippage FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(order_id) REFERENCES trade_orders (id)
);
CREATE INDEX ix_trade_fills_broker_fill_id ON trade_fills (broker_fill_id);
CREATE INDEX ix_trade_fills_symbol ON trade_fills (symbol);
CREATE INDEX ix_trade_fills_order_id ON trade_fills (order_id);
CREATE TABLE portfolio_cash_ledger (
	id INTEGER NOT NULL, 
	portfolio_id INTEGER, 
	created_at DATETIME, 
	entry_type VARCHAR(30), 
	amount FLOAT, 
	trade_order_id INTEGER, 
	notes TEXT, currency TEXT DEFAULT 'USD', 
	PRIMARY KEY (id), 
	FOREIGN KEY(trade_order_id) REFERENCES trade_orders (id)
);
CREATE INDEX ix_portfolio_cash_ledger_portfolio_id ON portfolio_cash_ledger (portfolio_id);
CREATE TABLE portfolio_snapshots (
	id INTEGER NOT NULL, 
	portfolio_id INTEGER, 
	as_of DATETIME, 
	cash FLOAT, 
	market_value FLOAT, 
	equity FLOAT, 
	realized_pnl FLOAT, 
	unrealized_pnl FLOAT, 
	net_pnl FLOAT, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_portfolio_snapshots_portfolio_id ON portfolio_snapshots (portfolio_id);
CREATE TABLE portfolio_positions (
	id INTEGER NOT NULL, 
	portfolio_id INTEGER NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	qty FLOAT NOT NULL, 
	avg_cost FLOAT NOT NULL, 
	market_price FLOAT NOT NULL, 
	market_value FLOAT NOT NULL, 
	unrealized_pnl FLOAT NOT NULL, 
	realized_pnl FLOAT NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(portfolio_id) REFERENCES portfolios (id)
);
CREATE INDEX ix_portfolio_positions_symbol ON portfolio_positions (symbol);
CREATE INDEX ix_portfolio_positions_portfolio_id ON portfolio_positions (portfolio_id);
CREATE TABLE closed_trades (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    opened_at DATETIME,
    closed_at DATETIME NOT NULL,
    entry_qty REAL DEFAULT 0.0,
    exit_qty REAL DEFAULT 0.0,
    entry_price REAL DEFAULT 0.0,
    exit_price REAL DEFAULT 0.0,
    gross_pnl REAL DEFAULT 0.0,
    net_pnl REAL DEFAULT 0.0,
    commission REAL DEFAULT 0.0,
    slippage REAL DEFAULT 0.0,
    holding_period_days REAL DEFAULT 0.0,
    side_open TEXT,
    side_close TEXT,
    notes TEXT
);
CREATE TABLE strategy_runs (
    id INTEGER PRIMARY KEY,
    portfolio_id INTEGER,
    strategy_name TEXT,
    trigger_type TEXT,
    status TEXT,
    target_snapshot TEXT,
    drift_threshold REAL,
    notes TEXT,
    created_at DATETIME
);
CREATE UNIQUE INDEX idx_snapshot_unique 
ON analytics_snapshots (tenant_id, symbol);
CREATE TABLE portfolio_nav_history (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    as_of DATE NOT NULL,

    nav REAL NOT NULL,
    cash REAL NOT NULL,
    market_value REAL NOT NULL,

    gross_exposure REAL DEFAULT 0,
    net_exposure REAL DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE rebalance_jobs (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    frequency TEXT NOT NULL,         -- 'daily' | 'weekly'
    day_of_week INTEGER,            -- 0=Mon ... 6=Sun (for weekly)
    last_run DATETIME,
    next_run DATETIME,
    threshold REAL DEFAULT 0.05,
    auto_execute INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX idx_nav_unique
ON portfolio_nav_history (portfolio_id, as_of);
CREATE TABLE portfolio_user_map (
    id TEXT PRIMARY KEY,
    portfolio_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT DEFAULT 'viewer', -- viewer | trader | owner
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE user_portfolios (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    portfolio_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, tenant_id TEXT,

    UNIQUE(user_id, portfolio_id)
);
