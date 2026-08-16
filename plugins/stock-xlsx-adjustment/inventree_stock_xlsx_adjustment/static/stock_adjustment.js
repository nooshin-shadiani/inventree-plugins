/** Render the bulk stock XLSX workflow inside InvenTree's stock page. */

const MAX_RENDERED_ROWS = 200;

const PERSIAN_MESSAGES = Object.freeze({
  'The request failed.': 'درخواست انجام نشد.',
  Rows: 'ردیف‌ها',
  Valid: 'معتبر',
  Errors: 'خطادار',
  Add: 'افزایش',
  Remove: 'کاهش',
  Count: 'موجودی‌گردانی',
  'Showing the first {count} rows.': 'فقط {count} ردیف نخست نمایش داده می‌شود.',
  Line: 'ردیف',
  'Stock item': 'شناسه موجودی',
  Part: 'قطعه',
  Location: 'مکان',
  Operation: 'عملیات',
  Quantity: 'مقدار',
  Current: 'موجودی فعلی',
  Result: 'موجودی پس از اعمال',
  Status: 'وضعیت',
  Ready: 'آماده',
  'Upload an XLSX file containing stock_item_id, operation, quantity, and optional notes. Preview validates every row without changing stock.':
    'یک فایل اکسل شامل ستون‌های stock_item_id، operation، quantity و در صورت نیاز notes بارگذاری کنید. پیش‌نمایش همهٔ ردیف‌ها را بدون تغییر موجودی بررسی می‌کند.',
  'XLSX file': 'فایل اکسل',
  'Download template': 'دریافت فایل نمونه',
  Preview: 'پیش‌نمایش',
  'Apply all rows': 'اعمال همهٔ ردیف‌ها',
  'Template downloaded.': 'فایل نمونه دریافت شد.',
  'Select an XLSX file first.': 'ابتدا یک فایل اکسل انتخاب کنید.',
  'Validating workbook...': 'در حال بررسی فایل اکسل…',
  'Preview passed. No stock has changed yet.':
    'پیش‌نمایش موفق بود؛ هنوز موجودی تغییر نکرده است.',
  'Fix every row error before applying the workbook.':
    'پیش از اعمال فایل، خطای همهٔ ردیف‌ها را برطرف کنید.',
  'Apply every stock adjustment in this workbook?':
    'همهٔ تغییرات موجودی این فایل اعمال شوند؟',
  'Applying workbook...': 'در حال اعمال تغییرات موجودی…',
  'Applied {count} stock adjustments.': '{count} تغییر موجودی اعمال شد.',
  'Stock item change permission is required.':
    'برای انجام این عملیات، دسترسی تغییر موجودی لازم است.',
  'An XLSX file is required.': 'انتخاب فایل اکسل الزامی است.',
  'Quantity must be greater than zero for add and remove operations.':
    'برای عملیات افزایش و کاهش، مقدار باید بیشتر از صفر باشد.',
  'Upload an .xlsx file.': 'یک فایل با پسوند «.xlsx» بارگذاری کنید.',
  'Data file exceeds the maximum size limit.':
    'حجم فایل از حداکثر مجاز بیشتر است.',
  'Could not read the XLSX file.': 'خواندن فایل اکسل ممکن نبود.',
  'Data file contains no headers.': 'فایل اکسل سطر عنوان ندارد.',
  'Data file has too many columns.': 'تعداد ستون‌های فایل بیش از حد مجاز است.',
  'Data file has too many rows.': 'تعداد ردیف‌های فایل بیش از حد مجاز است.',
  'Data file contains no adjustment rows.':
    'فایل اکسل هیچ ردیفی برای تغییر موجودی ندارد.',
  'Stock item appears more than once; combine it into one row.':
    'یک رکورد موجودی بیش از یک بار آمده است؛ آن را در یک ردیف ادغام کنید.',
  'Serialized stock items only support a count operation with quantity 1.':
    'برای موجودی سریال‌دار فقط عملیات شمارش با مقدار ۱ مجاز است.',
  'Removal quantity exceeds available stock.':
    'مقدار کسرشده از موجودی فعلی بیشتر است.',
  'Resulting quantity exceeds the supported stock precision.':
    'دقت مقدار نهایی از دقت پشتیبانی‌شدهٔ موجودی بیشتر است.',
  'Stock item does not exist.': 'رکورد موجودی وجود ندارد.',
  'Stock item is not currently in stock.': 'این رکورد در حال حاضر موجود نیست.'
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
  if (options.type) node.type = options.type;
  if (options.accept) node.accept = options.accept;
  if (options.disabled !== undefined) node.disabled = options.disabled;
  if (options.style) Object.assign(node.style, options.style);
  for (const [name, value] of Object.entries(options.attributes || {})) {
    node.setAttribute(name, value);
  }
  if (text !== null) node.textContent = text;

  return node;
}

function button(label, primary = false) {
  return element(
    'button',
    {
      type: 'button',
      style: {
        border: primary ? '1px solid #228be6' : '1px solid #ced4da',
        borderRadius: '4px',
        background: primary ? '#228be6' : 'transparent',
        color: primary ? '#fff' : 'inherit',
        cursor: 'pointer',
        padding: '8px 14px'
      }
    },
    label
  );
}

function describeError(error, t) {
  const data = error?.response?.data;

  if (typeof data === 'string') return t(data);
  if (data?.detail) return t(String(data.detail));
  if (data?.file) {
    const messages = Array.isArray(data.file) ? data.file : [data.file];
    return messages.map((message) => t(String(message))).join(' ');
  }

  if (data && typeof data === 'object') return JSON.stringify(data);
  return t(error?.message || 'The request failed.');
}

function formatCount(value, locale) {
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return new Intl.NumberFormat(locale || 'en').format(number);
}

function renderResult(target, result, t, locale) {
  target.replaceChildren();

  const summary = element('div', {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: '16px',
      margin: '12px 0'
    }
  });

  const fields = [
    ['Rows', result.total_rows],
    ['Valid', result.valid_rows],
    ['Errors', result.error_rows],
    ['Add', result.operation_counts?.add || 0],
    ['Remove', result.operation_counts?.remove || 0],
    ['Count', result.operation_counts?.count || 0]
  ];

  for (const [label, value] of fields) {
    const item = element('span');
    const strong = element('strong', {}, `${t(label)}: `);
    item.append(strong, document.createTextNode(formatCount(value, locale)));
    summary.append(item);
  }

  target.append(summary);

  if (result.rows.length > MAX_RENDERED_ROWS) {
    target.append(
      element(
        'p',
        { style: { color: '#868e96' } },
        t('Showing the first {count} rows.', {
          count: formatCount(MAX_RENDERED_ROWS, locale)
        })
      )
    );
  }

  const wrapper = element('div', {
    attributes: {
      role: 'region',
      'aria-label': t('Preview')
    },
    style: { overflowX: 'auto', maxWidth: '100%' }
  });
  const table = element('table', {
    style: { borderCollapse: 'collapse', width: '100%', fontSize: '0.9rem' }
  });
  const head = element('thead');
  const headerRow = element('tr');
  const headers = [
    'Line',
    'Stock item',
    'Part',
    'Location',
    'Operation',
    'Quantity',
    'Current',
    'Result',
    'Status'
  ];

  for (const label of headers) {
    headerRow.append(
      element(
        'th',
        {
          attributes: { scope: 'col' },
          style: {
            borderBottom: '1px solid #ced4da',
            padding: '8px',
            textAlign: 'start',
            whiteSpace: 'nowrap'
          }
        },
        t(label)
      )
    );
  }

  head.append(headerRow);
  table.append(head);
  const body = element('tbody');
  const operationLabels = { add: 'Add', remove: 'Remove', count: 'Count' };

  for (const row of result.rows.slice(0, MAX_RENDERED_ROWS)) {
    const tr = element('tr');
    const values = [
      row.line,
      row.stock_item_id ?? '',
      row.part ?? '',
      row.location ?? '',
      t(operationLabels[row.operation] || row.operation),
      row.quantity ?? '',
      row.current_quantity ?? '',
      row.resulting_quantity ?? '',
      row.valid ? t('Ready') : row.errors.map((message) => t(message)).join(' ')
    ];

    for (const [index, value] of values.entries()) {
      tr.append(
        element(
          'td',
          {
            style: {
              borderBottom: '1px solid #e9ecef',
              color: index === values.length - 1 && !row.valid ? '#c92a2a' : 'inherit',
              padding: '8px',
              verticalAlign: 'top'
            }
          },
          String(value)
        )
      );
    }

    body.append(tr);
  }

  table.append(body);
  wrapper.append(table);
  target.append(wrapper);
}

export function renderPanel(container, context) {
  const urls = context.context || {};
  const locale = context.locale || 'en';
  const t = createTranslator(locale);
  let previewedFile = null;
  let busy = false;

  const root = element('div', {
    attributes: {
      dir: localeRoot(locale) === 'fa' ? 'rtl' : 'ltr',
      lang: locale
    },
    style: { padding: '4px' }
  });
  const intro = element(
    'p',
    {},
    t(
      'Upload an XLSX file containing stock_item_id, operation, quantity, and optional notes. Preview validates every row without changing stock.'
    )
  );
  const controls = element('div', {
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }
  });
  const fileInput = element('input', {
    type: 'file',
    accept: '.xlsx',
    attributes: { 'aria-label': t('XLSX file') }
  });
  const templateButton = button(t('Download template'));
  const previewButton = button(t('Preview'));
  const applyButton = button(t('Apply all rows'), true);
  applyButton.disabled = true;

  const statusBox = element('p', {
    attributes: { role: 'status', 'aria-live': 'polite' },
    style: { minHeight: '1.5em' }
  });
  const resultBox = element('div');

  function setStatus(message, error = false) {
    statusBox.textContent = message;
    statusBox.style.color = error ? '#c92a2a' : '#2b8a3e';
  }

  function setBusy(value) {
    busy = value;
    fileInput.disabled = value;
    templateButton.disabled = value;
    previewButton.disabled = value;
    applyButton.disabled = value || previewedFile === null;
  }

  function uploadForm(file) {
    const form = new FormData();
    form.append('file', file);
    return form;
  }

  fileInput.addEventListener('change', () => {
    previewedFile = null;
    applyButton.disabled = true;
    resultBox.replaceChildren();
    setStatus('');
  });

  templateButton.addEventListener('click', async () => {
    if (busy) return;
    setBusy(true);

    try {
      const response = await context.api.get(urls.template_url, {
        responseType: 'blob',
        timeout: 60000
      });
      const objectUrl = URL.createObjectURL(response.data);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = 'inventree-stock-adjustments.xlsx';
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
      setStatus(t('Template downloaded.'));
    } catch (error) {
      setStatus(describeError(error, t), true);
    } finally {
      setBusy(false);
    }
  });

  previewButton.addEventListener('click', async () => {
    const file = fileInput.files?.[0];
    if (!file || busy) {
      if (!file) setStatus(t('Select an XLSX file first.'), true);
      return;
    }

    previewedFile = null;
    setBusy(true);
    setStatus(t('Validating workbook...'));

    try {
      const response = await context.api.post(
        urls.preview_url,
        uploadForm(file),
        { timeout: 60000 }
      );
      renderResult(resultBox, response.data, t, locale);

      if (response.data.can_apply) {
        previewedFile = file;
        setStatus(t('Preview passed. No stock has changed yet.'));
      } else {
        setStatus(t('Fix every row error before applying the workbook.'), true);
      }
    } catch (error) {
      resultBox.replaceChildren();
      setStatus(describeError(error, t), true);
    } finally {
      setBusy(false);
    }
  });

  applyButton.addEventListener('click', async () => {
    if (!previewedFile || busy) return;
    if (!window.confirm(t('Apply every stock adjustment in this workbook?'))) return;

    const file = previewedFile;
    setBusy(true);
    setStatus(t('Applying workbook...'));

    try {
      const response = await context.api.post(urls.apply_url, uploadForm(file));
      renderResult(resultBox, response.data, t, locale);
      previewedFile = null;
      await context.queryClient.invalidateQueries();
      setStatus(
        t('Applied {count} stock adjustments.', {
          count: formatCount(response.data.valid_rows, locale)
        })
      );
    } catch (error) {
      const result = error?.response?.data;
      if (result?.rows) renderResult(resultBox, result, t, locale);
      previewedFile = null;
      setStatus(describeError(error, t), true);
    } finally {
      setBusy(false);
    }
  });

  controls.append(fileInput, templateButton, previewButton, applyButton);
  root.append(intro, controls, statusBox, resultBox);
  container.replaceChildren(root);
}
