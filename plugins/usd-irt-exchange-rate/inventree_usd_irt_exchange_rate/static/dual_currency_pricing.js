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

const PERSIAN_MESSAGES = Object.freeze({
  'Overall pricing': 'قیمت کلی',
  'Override pricing': 'قیمت دستی',
  'Internal pricing': 'قیمت داخلی',
  'BOM pricing': 'هزینهٔ فهرست مواد',
  'Purchase pricing': 'هزینهٔ خرید',
  'Supplier pricing': 'قیمت تأمین‌کننده',
  'Variant pricing': 'هزینهٔ گونه‌ها',
  'Sale pricing': 'قیمت فروش',
  'Sale history': 'سابقهٔ فروش',
  'Current calculated part pricing': 'قیمت محاسبه‌شدهٔ فعلی قطعه',
  'Pricing source': 'مبنای قیمت',
  'Minimum USD': 'حداقل دلار (USD)',
  'Maximum USD': 'حداکثر دلار (USD)',
  'Minimum IRT': 'حداقل تومان (IRT)',
  'Maximum IRT': 'حداکثر تومان (IRT)',
  'No calculated pricing is available for this part.':
    'هنوز قیمت محاسبه‌شده‌ای برای این قطعه وجود ندارد.',
  'Latest saved price for each source': 'آخرین قیمت ذخیره‌شده برای هر منبع',
  Source: 'منبع',
  'Entered value': 'مقدار ثبت‌شده',
  'USD at save': 'دلار هنگام ثبت',
  'IRT at save': 'تومان هنگام ثبت',
  'IRT per USD': 'تومان به ازای دلار',
  Captured: 'زمان ثبت',
  'No saved price snapshots are available yet.':
    'هنوز سابقهٔ ذخیره‌شده‌ای از قیمت‌ها وجود ندارد.',
  Converted: 'تبدیل‌شده',
  'Missing exchange rate': 'نرخ تبدیل موجود نیست',
  'Unsupported currency': 'واحد پول پشتیبانی نمی‌شود',
  'Exchange rate summary': 'خلاصهٔ نرخ تبدیل',
  '1 USD = {rate}': '۱ دلار (USD) = {rate}',
  'No applied USD to IRT rate is available.':
    'هنوز نرخ دلار به تومان اعمال نشده است.',
  'Exchange rate updated: {date}': 'آخرین به‌روزرسانی نرخ تبدیل: {date}',
  'Part pricing updated: {date}': 'آخرین به‌روزرسانی قیمت قطعه: {date}',
  'The request failed.': 'درخواست انجام نشد.',
  'Could not load USD / IRT pricing: {detail}':
    'بارگذاری قیمت دلار و تومان ممکن نبود: {detail}',
  'Loading USD / IRT pricing…': 'در حال بارگذاری قیمت دلار و تومان…',
  'Part view permission is required.':
    'برای مشاهدهٔ این اطلاعات، دسترسی مشاهدهٔ قطعه لازم است.',
  USD: 'دلار (USD)',
  IRT: 'تومان (IRT)'
});

function localeRoot(locale) {
  return String(locale || 'en').replace('_', '-').split('-')[0].toLowerCase();
}

function createTranslator(locale) {
  const messages = localeRoot(locale) === 'fa' ? PERSIAN_MESSAGES : {};

  return (message, values = {}) => {
    let output = messages[message] || message;

    for (const [key, value] of Object.entries(values)) {
      output = output.replaceAll(`{${key}}`, String(value));
    }

    return output;
  };
}

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

function formatMoney(value, currency, locale, t) {
  const number = numeric(value);
  if (number === null) return '—';

  if (currency === 'USD' && localeRoot(locale) !== 'fa') {
    return new Intl.NumberFormat(locale || 'en', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 2
    }).format(number);
  }

  return `${formatNumber(number, locale, 2)} ${t(currency)}`;
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
  return element(
    header ? 'th' : 'td',
    {
      attributes: header ? { scope: 'col' } : {},
      style: {
        borderBottom: '1px solid var(--mantine-color-default-border)',
        padding: '8px',
        textAlign: 'start',
        verticalAlign: 'top',
        whiteSpace: header ? 'nowrap' : 'normal'
      }
    },
    value
  );
}

function tableShell(captionText, headers) {
  const wrapper = element('div', {
    attributes: { tabindex: '0', role: 'region', 'aria-label': captionText },
    style: { maxWidth: '100%', overflowX: 'auto' }
  });
  const table = element('table', {
    style: { borderCollapse: 'collapse', minWidth: '760px', width: '100%' }
  });
  const caption = element(
    'caption',
    { style: { fontWeight: '600', padding: '8px', textAlign: 'start' } },
    captionText
  );
  const head = element('thead');
  const row = element('tr');

  for (const header of headers) row.append(tableCell(header, true));
  head.append(row);
  table.append(caption, head);
  wrapper.append(table);
  return { wrapper, table };
}

function currentPricingTable(pricing, rate, locale, t) {
  const { wrapper, table } = tableShell(t('Current calculated part pricing'), [
    t('Pricing source'),
    t('Minimum USD'),
    t('Maximum USD'),
    t('Minimum IRT'),
    t('Maximum IRT')
  ]);
  const body = element('tbody');
  let rowCount = 0;

  for (const [label, minimumField, maximumField] of PRICING_ROWS) {
    const minimum = pricing[minimumField];
    const maximum = pricing[maximumField];
    if (numeric(minimum) === null && numeric(maximum) === null) continue;

    const minimumCurrency =
      minimumField === 'override_min'
        ? pricing.override_min_currency || pricing.currency
        : pricing.currency;
    const maximumCurrency =
      maximumField === 'override_max'
        ? pricing.override_max_currency || pricing.currency
        : pricing.currency;
    const minimumPair = convertPair(minimum, minimumCurrency, rate);
    const maximumPair = convertPair(maximum, maximumCurrency, rate);
    const row = element('tr');

    row.append(
      tableCell(t(label)),
      tableCell(formatMoney(minimumPair.USD, 'USD', locale, t)),
      tableCell(formatMoney(maximumPair.USD, 'USD', locale, t)),
      tableCell(formatMoney(minimumPair.IRT, 'IRT', locale, t)),
      tableCell(formatMoney(maximumPair.IRT, 'IRT', locale, t))
    );
    body.append(row);
    rowCount += 1;
  }

  if (rowCount === 0) {
    const row = element('tr');
    const empty = tableCell(t('No calculated pricing is available for this part.'));
    empty.colSpan = 5;
    row.append(empty);
    body.append(row);
  }

  table.append(body);
  return wrapper;
}

function conversionStatus(status, t) {
  const labels = {
    converted: 'Converted',
    missing_rate: 'Missing exchange rate',
    unsupported_currency: 'Unsupported currency'
  };

  return t(labels[status] || String(status).replaceAll('_', ' '));
}

function historyTable(rows, locale, t) {
  const { wrapper, table } = tableShell(t('Latest saved price for each source'), [
    t('Source'),
    t('Entered value'),
    t('USD at save'),
    t('IRT at save'),
    t('IRT per USD'),
    t('Captured')
  ]);
  const body = element('tbody');

  for (const record of rows) {
    const row = element('tr');
    const source =
      record.conversion_status === 'converted'
        ? record.source
        : `${record.source} (${conversionStatus(record.conversion_status, t)})`;
    row.append(
      tableCell(source),
      tableCell(
        formatMoney(record.original_amount, record.original_currency, locale, t)
      ),
      tableCell(formatMoney(record.amount_usd, 'USD', locale, t)),
      tableCell(formatMoney(record.amount_irt, 'IRT', locale, t)),
      tableCell(formatNumber(record.usd_to_irt_rate, locale, 2)),
      tableCell(formatDate(record.captured_at, locale))
    );
    body.append(row);
  }

  if (rows.length === 0) {
    const row = element('tr');
    const empty = tableCell(t('No saved price snapshots are available yet.'));
    empty.colSpan = 6;
    row.append(empty);
    body.append(row);
  }

  table.append(body);
  return wrapper;
}

function summary(exchange, pricing, rate, locale, t) {
  const box = element('section', {
    attributes: { 'aria-label': t('Exchange rate summary') },
    style: {
      border: '1px solid var(--mantine-color-default-border)',
      borderRadius: 'var(--mantine-radius-sm)',
      padding: '12px'
    }
  });
  const rateText = rate
    ? t('1 USD = {rate}', { rate: formatMoney(rate, 'IRT', locale, t) })
    : t('No applied USD to IRT rate is available.');
  box.append(
    element('strong', {}, rateText),
    element(
      'div',
      { style: { color: 'var(--mantine-color-dimmed)', marginTop: '4px' } },
      t('Exchange rate updated: {date}', {
        date: formatDate(exchange.updated, locale)
      })
    ),
    element(
      'div',
      { style: { color: 'var(--mantine-color-dimmed)' } },
      t('Part pricing updated: {date}', {
        date: formatDate(pricing.updated, locale)
      })
    )
  );
  return box;
}

function renderError(container, error, t) {
  const detail = error?.response?.data?.detail || error?.message || 'The request failed.';
  container.replaceChildren(
    element(
      'div',
      {
        attributes: { role: 'alert' },
        style: {
          border: '1px solid var(--mantine-color-red-6)',
          borderRadius: 'var(--mantine-radius-sm)',
          color: 'var(--mantine-color-red-7)',
          padding: '12px'
        }
      },
      t('Could not load USD / IRT pricing: {detail}', { detail: t(String(detail)) })
    )
  );
}

export async function renderPanel(container, context) {
  if (!container) return;

  const urls = context.context || {};
  const locale = context.locale || 'en';
  const t = createTranslator(locale);
  container.dir = localeRoot(locale) === 'fa' ? 'rtl' : 'ltr';
  container.lang = locale;
  container.replaceChildren(
    element(
      'p',
      { attributes: { role: 'status', 'aria-live': 'polite' } },
      t('Loading USD / IRT pricing…')
    )
  );

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
      attributes: {
        dir: localeRoot(locale) === 'fa' ? 'rtl' : 'ltr',
        lang: locale
      },
      style: { display: 'grid', gap: '16px', padding: '4px' }
    });

    root.append(
      summary(exchange, pricing, rate, locale, t),
      currentPricingTable(pricing, rate, locale, t),
      historyTable(history, locale, t)
    );
    container.replaceChildren(root);
  } catch (error) {
    if (container.isConnected) renderError(container, error, t);
  }
}
