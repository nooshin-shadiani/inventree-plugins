/** Render immutable USD and Iranian-toman pairs captured at price save time. */

const PERSIAN_MESSAGES = Object.freeze({
  'Saved USD / IRT prices': 'قیمت‌های ذخیره‌شدهٔ دلار و تومان',
  'The paired USD and IRT values are frozen when a source price is saved. Later exchange-rate updates do not change them.':
    'مقادیر جفت دلار و تومان هنگام ذخیرهٔ قیمت ثابت می‌شوند و به‌روزرسانی‌های بعدی نرخ ارز آن‌ها را تغییر نمی‌دهد.',
  'Latest frozen price for each source': 'آخرین قیمت ثابت‌شده برای هر منبع',
  'Frozen purchase-order unit prices': 'قیمت واحد ثابت‌شدهٔ سفارش خرید',
  Source: 'منبع',
  Item: 'کالا',
  Quantity: 'تعداد',
  'Entered value': 'مقدار ثبت‌شده',
  'Entered unit': 'قیمت واحد ثبت‌شده',
  'USD at save': 'دلار هنگام ثبت',
  'IRT at save': 'تومان هنگام ثبت',
  'Unit USD': 'قیمت واحد دلار',
  'Unit IRT': 'قیمت واحد تومان',
  'IRT per USD': 'تومان به ازای دلار',
  Captured: 'زمان ثبت',
  'No saved price snapshots are available yet.':
    'هنوز سابقهٔ ذخیره‌شده‌ای از قیمت‌ها وجود ندارد.',
  'No purchase-order prices are available yet.':
    'هنوز قیمتی برای ردیف‌های سفارش خرید ثبت نشده است.',
  Converted: 'تبدیل‌شده',
  'Missing exchange rate': 'نرخ تبدیل موجود نیست',
  'Unsupported currency': 'واحد پول پشتیبانی نمی‌شود',
  'The request failed.': 'درخواست انجام نشد.',
  'Could not load USD / IRT pricing: {detail}':
    'بارگذاری قیمت دلار و تومان ممکن نبود: {detail}',
  'Loading USD / IRT pricing…': 'در حال بارگذاری قیمت دلار و تومان…',
  'Part view permission is required.':
    'برای مشاهدهٔ این اطلاعات، دسترسی مشاهدهٔ قطعه لازم است.',
  'Stock item view permission is required.':
    'برای مشاهدهٔ این اطلاعات، دسترسی مشاهدهٔ موجودی لازم است.',
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

function tableShell(captionText, headers, minWidth = '760px') {
  const wrapper = element('div', {
    attributes: { tabindex: '0', role: 'region', 'aria-label': captionText },
    style: { maxWidth: '100%', overflowX: 'auto' }
  });
  const table = element('table', {
    style: { borderCollapse: 'collapse', minWidth, width: '100%' }
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

function conversionStatus(status, t) {
  const labels = {
    converted: 'Converted',
    missing_rate: 'Missing exchange rate',
    unsupported_currency: 'Unsupported currency'
  };

  return t(labels[status] || String(status).replaceAll('_', ' '));
}

function historyTable(rows, locale, t) {
  const { wrapper, table } = tableShell(t('Latest frozen price for each source'), [
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

function purchaseOrderTable(rows, locale, t) {
  const { wrapper, table } = tableShell(
    t('Frozen purchase-order unit prices'),
    [
      t('Item'),
      t('Quantity'),
      t('Entered unit'),
      t('Unit USD'),
      t('Unit IRT'),
      t('IRT per USD'),
      t('Captured')
    ],
    '900px'
  );
  const body = element('tbody');

  for (const record of rows) {
    const row = element('tr');
    const itemParts = [record.supplier_sku, record.part_name].filter(Boolean);
    let item = itemParts.join(' — ') || `#${record.line_item}`;

    if (record.conversion_status !== 'converted') {
      item = `${item} (${conversionStatus(record.conversion_status, t)})`;
    }

    row.append(
      tableCell(item),
      tableCell(formatNumber(record.quantity, locale, 5)),
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
    const empty = tableCell(t('No purchase-order prices are available yet.'));
    empty.colSpan = 7;
    row.append(empty);
    body.append(row);
  }

  table.append(body);
  return wrapper;
}

function frozenPriceNotice(t) {
  const box = element('section', {
    attributes: { 'aria-label': t('Saved USD / IRT prices') },
    style: {
      border: '1px solid var(--mantine-color-default-border)',
      borderRadius: 'var(--mantine-radius-sm)',
      padding: '12px'
    }
  });
  box.append(
    element('strong', {}, t('Saved USD / IRT prices')),
    element(
      'div',
      { style: { color: 'var(--mantine-color-dimmed)', marginTop: '4px' } },
      t(
        'The paired USD and IRT values are frozen when a source price is saved. Later exchange-rate updates do not change them.'
      )
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
    const historyResponse = await context.api.get(urls.history_url);
    if (!container.isConnected) return;

    const history = historyResponse.data?.results || [];
    const root = element('div', {
      attributes: {
        dir: localeRoot(locale) === 'fa' ? 'rtl' : 'ltr',
        lang: locale
      },
      style: { display: 'grid', gap: '16px', padding: '4px' }
    });

    const table =
      urls.view === 'purchaseorder'
        ? purchaseOrderTable(history, locale, t)
        : historyTable(history, locale, t);

    root.append(frozenPriceNotice(t), table);
    container.replaceChildren(root);
  } catch (error) {
    if (container.isConnected) renderError(container, error, t);
  }
}
