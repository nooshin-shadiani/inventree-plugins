/** Render current and saved part prices in USD and Iranian toman. */

const PRICING_ROWS = [
  ['Overall pricing', 'overall_min', 'overall_max'],
  ['Override pricing', 'override_min', 'override_max'],
  ['Internal pricing', 'internal_cost_min', 'internal_cost_max'],
  ['BOM pricing', 'bom_cost_min', 'bom_cost_max'],
  ['Purchase pricing', 'purchase_cost_min', 'purchase_cost_max'],
  ['Supplier pricing', 'supplier_price_min', 'supplier_price_max'],
  ['Variant pricing', 'variant_cost_min', 'variant_cost_max'],
  ['Sale pricing', 'sale_price_min', 'sale_price_max'],
  ['Sale history', 'sale_history_min', 'sale_history_max']
];

function element(tag, options = {}, text = null) {
  const node = document.createElement(tag);

  if (options.className) node.className = options.className;
  if (options.style) Object.assign(node.style, options.style);
  for (const [name, value] of Object.entries(options.attributes || {})) {
    node.setAttribute(name, value);
  }
  if (text !== null) node.textContent = text;

  return node;
}

function numeric(value) {
  if (value === null || value === undefined || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value, locale, maximumFractionDigits = 2) {
  const number = numeric(value);
  if (number === null) return '—';

  return new Intl.NumberFormat(locale || 'en', {
    maximumFractionDigits,
    minimumFractionDigits: 0
  }).format(number);
}

function formatMoney(value, currency, locale) {
  const number = numeric(value);
  if (number === null) return '—';

  if (currency === 'USD') {
    return new Intl.NumberFormat(locale || 'en', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 2
    }).format(number);
  }

  return `${formatNumber(number, locale, 2)} ${currency}`;
}

function formatDate(value, locale) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(locale || 'en', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
}

function convertPair(value, currency, rate) {
  const amount = numeric(value);
  if (amount === null) return { USD: null, IRT: null };

  if (currency === 'USD') {
    return { USD: amount, IRT: rate ? amount * rate : null };
  }
  if (currency === 'IRT') {
    return { USD: rate ? amount / rate : null, IRT: amount };
  }

  return { USD: null, IRT: null };
}

function tableCell(value, header = false) {
  return element(header ? 'th' : 'td', {
    attributes: header ? { scope: 'col' } : {},
    style: {
      borderBottom: '1px solid var(--mantine-color-default-border)',
      padding: '8px',
      textAlign: 'start',
      verticalAlign: 'top',
      whiteSpace: header ? 'nowrap' : 'normal'
    }
  }, value);
}

function tableShell(captionText, headers) {
  const wrapper = element('div', {
    attributes: { tabindex: '0', role: 'region', 'aria-label': captionText },
    style: { maxWidth: '100%', overflowX: 'auto' }
  });
  const table = element('table', {
    style: { borderCollapse: 'collapse', minWidth: '760px', width: '100%' }
  });
  const caption = element('caption', {
    style: { fontWeight: '600', padding: '8px', textAlign: 'start' }
  }, captionText);
  const head = element('thead');
  const row = element('tr');

  for (const header of headers) row.append(tableCell(header, true));
  head.append(row);
  table.append(caption, head);
  wrapper.append(table);
  return { wrapper, table };
}

function currentPricingTable(pricing, rate, locale) {
  const { wrapper, table } = tableShell('Current calculated part pricing', [
    'Pricing source',
    'Minimum USD',
    'Maximum USD',
    'Minimum IRT',
    'Maximum IRT'
  ]);
  const body = element('tbody');
  let rowCount = 0;

  for (const [label, minimumField, maximumField] of PRICING_ROWS) {
    const minimum = pricing[minimumField];
    const maximum = pricing[maximumField];
    if (numeric(minimum) === null && numeric(maximum) === null) continue;

    const minimumCurrency = minimumField === 'override_min'
      ? pricing.override_min_currency || pricing.currency
      : pricing.currency;
    const maximumCurrency = maximumField === 'override_max'
      ? pricing.override_max_currency || pricing.currency
      : pricing.currency;
    const minimumPair = convertPair(minimum, minimumCurrency, rate);
    const maximumPair = convertPair(maximum, maximumCurrency, rate);
    const row = element('tr');

    row.append(
      tableCell(label),
      tableCell(formatMoney(minimumPair.USD, 'USD', locale)),
      tableCell(formatMoney(maximumPair.USD, 'USD', locale)),
      tableCell(formatMoney(minimumPair.IRT, 'IRT', locale)),
      tableCell(formatMoney(maximumPair.IRT, 'IRT', locale))
    );
    body.append(row);
    rowCount += 1;
  }

  if (rowCount === 0) {
    const row = element('tr');
    const empty = tableCell('No calculated pricing is available for this part.');
    empty.colSpan = 5;
    row.append(empty);
    body.append(row);
  }

  table.append(body);
  return wrapper;
}

function historyTable(rows, locale) {
  const { wrapper, table } = tableShell('Latest saved price for each source', [
    'Source',
    'Entered value',
    'USD at save',
    'IRT at save',
    'IRT per USD',
    'Captured'
  ]);
  const body = element('tbody');

  for (const record of rows) {
    const row = element('tr');
    const source = record.conversion_status === 'converted'
      ? record.source
      : `${record.source} (${record.conversion_status.replaceAll('_', ' ')})`;
    row.append(
      tableCell(source),
      tableCell(formatMoney(
        record.original_amount,
        record.original_currency,
        locale
      )),
      tableCell(formatMoney(record.amount_usd, 'USD', locale)),
      tableCell(formatMoney(record.amount_irt, 'IRT', locale)),
      tableCell(formatNumber(record.usd_to_irt_rate, locale, 2)),
      tableCell(formatDate(record.captured_at, locale))
    );
    body.append(row);
  }

  if (rows.length === 0) {
    const row = element('tr');
    const empty = tableCell('No saved price snapshots are available yet.');
    empty.colSpan = 6;
    row.append(empty);
    body.append(row);
  }

  table.append(body);
  return wrapper;
}

function summary(exchange, pricing, rate, locale) {
  const box = element('section', {
    attributes: { 'aria-label': 'Exchange rate summary' },
    style: {
      border: '1px solid var(--mantine-color-default-border)',
      borderRadius: 'var(--mantine-radius-sm)',
      padding: '12px'
    }
  });
  const rateText = rate
    ? `1 USD = ${formatMoney(rate, 'IRT', locale)}`
    : 'No applied USD to IRT rate is available.';
  box.append(
    element('strong', {}, rateText),
    element('div', {
      style: { color: 'var(--mantine-color-dimmed)', marginTop: '4px' }
    }, `Exchange rate updated: ${formatDate(exchange.updated, locale)}`),
    element('div', {
      style: { color: 'var(--mantine-color-dimmed)' }
    }, `Part pricing updated: ${formatDate(pricing.updated, locale)}`)
  );
  return box;
}

function renderError(container, error) {
  const detail = error?.response?.data?.detail || error?.message || 'The request failed.';
  container.replaceChildren(element('div', {
    attributes: { role: 'alert' },
    style: {
      border: '1px solid var(--mantine-color-red-6)',
      borderRadius: 'var(--mantine-radius-sm)',
      color: 'var(--mantine-color-red-7)',
      padding: '12px'
    }
  }, `Could not load USD / IRT pricing: ${detail}`));
}

export async function renderPanel(container, context) {
  if (!container) return;

  const urls = context.context || {};
  const locale = context.locale || 'en';
  container.replaceChildren(element('p', {
    attributes: { role: 'status', 'aria-live': 'polite' }
  }, 'Loading USD / IRT pricing…'));

  try {
    const [pricingResponse, exchangeResponse, historyResponse] = await Promise.all([
      context.api.get(urls.pricing_url),
      context.api.get(urls.exchange_url),
      context.api.get(urls.history_url)
    ]);
    if (!container.isConnected) return;

    const pricing = pricingResponse.data || {};
    const exchange = exchangeResponse.data || {};
    const history = historyResponse.data?.results || [];
    const rateValue = numeric(exchange.exchange_rates?.IRT);
    const rate = rateValue && rateValue > 0 ? rateValue : null;
    const root = element('div', {
      style: { display: 'grid', gap: '16px', padding: '4px' }
    });

    root.append(
      summary(exchange, pricing, rate, locale),
      currentPricingTable(pricing, rate, locale),
      historyTable(history, locale)
    );
    container.replaceChildren(root);
  } catch (error) {
    if (container.isConnected) renderError(container, error);
  }
}
