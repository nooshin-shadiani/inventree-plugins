/** Render the bulk stock XLSX workflow inside InvenTree's stock page. */

const MAX_RENDERED_ROWS = 200;

function element(tag, options = {}, text = null) {
  const node = document.createElement(tag);

  if (options.className) node.className = options.className;
  if (options.type) node.type = options.type;
  if (options.accept) node.accept = options.accept;
  if (options.disabled !== undefined) node.disabled = options.disabled;
  if (options.style) Object.assign(node.style, options.style);
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

function describeError(error) {
  const data = error?.response?.data;

  if (typeof data === 'string') return data;
  if (data?.detail) return String(data.detail);
  if (data?.file) {
    return Array.isArray(data.file) ? data.file.join(' ') : String(data.file);
  }

  if (data && typeof data === 'object') return JSON.stringify(data);
  return error?.message || 'The request failed.';
}

function renderResult(target, result) {
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
    const strong = element('strong', {}, `${label}: `);
    item.append(strong, document.createTextNode(String(value)));
    summary.append(item);
  }

  target.append(summary);

  if (result.rows.length > MAX_RENDERED_ROWS) {
    target.append(
      element(
        'p',
        { style: { color: '#868e96' } },
        `Showing the first ${MAX_RENDERED_ROWS} rows.`
      )
    );
  }

  const wrapper = element('div', {
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
          style: {
            borderBottom: '1px solid #ced4da',
            padding: '8px',
            textAlign: 'left',
            whiteSpace: 'nowrap'
          }
        },
        label
      )
    );
  }

  head.append(headerRow);
  table.append(head);
  const body = element('tbody');

  for (const row of result.rows.slice(0, MAX_RENDERED_ROWS)) {
    const tr = element('tr');
    const values = [
      row.line,
      row.stock_item_id ?? '',
      row.part ?? '',
      row.location ?? '',
      row.operation,
      row.quantity ?? '',
      row.current_quantity ?? '',
      row.resulting_quantity ?? '',
      row.valid ? 'Ready' : row.errors.join(' ')
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
  let previewedFile = null;
  let busy = false;

  const root = element('div', { style: { padding: '4px' } });
  const intro = element(
    'p',
    {},
    'Upload an XLSX file containing stock_item_id, operation, quantity, and optional notes. Preview validates every row without changing stock.'
  );
  const controls = element('div', {
    style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }
  });
  const fileInput = element('input', { type: 'file', accept: '.xlsx' });
  const templateButton = button('Download template');
  const previewButton = button('Preview');
  const applyButton = button('Apply all rows', true);
  applyButton.disabled = true;

  const statusBox = element('p', { style: { minHeight: '1.5em' } });
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
      setStatus('Template downloaded.');
    } catch (error) {
      setStatus(describeError(error), true);
    } finally {
      setBusy(false);
    }
  });

  previewButton.addEventListener('click', async () => {
    const file = fileInput.files?.[0];
    if (!file || busy) {
      if (!file) setStatus('Select an XLSX file first.', true);
      return;
    }

    previewedFile = null;
    setBusy(true);
    setStatus('Validating workbook...');

    try {
      const response = await context.api.post(
        urls.preview_url,
        uploadForm(file),
        { timeout: 60000 }
      );
      renderResult(resultBox, response.data);

      if (response.data.can_apply) {
        previewedFile = file;
        setStatus('Preview passed. No stock has changed yet.');
      } else {
        setStatus('Fix every row error before applying the workbook.', true);
      }
    } catch (error) {
      resultBox.replaceChildren();
      setStatus(describeError(error), true);
    } finally {
      setBusy(false);
    }
  });

  applyButton.addEventListener('click', async () => {
    if (!previewedFile || busy) return;
    if (!window.confirm('Apply every stock adjustment in this workbook?')) return;

    const file = previewedFile;
    setBusy(true);
    setStatus('Applying workbook...');

    try {
      const response = await context.api.post(urls.apply_url, uploadForm(file));
      renderResult(resultBox, response.data);
      previewedFile = null;
      await context.queryClient.invalidateQueries();
      setStatus(`Applied ${response.data.valid_rows} stock adjustments.`);
    } catch (error) {
      const result = error?.response?.data;
      if (result?.rows) renderResult(resultBox, result);
      previewedFile = null;
      setStatus(describeError(error), true);
    } finally {
      setBusy(false);
    }
  });

  controls.append(fileInput, templateButton, previewButton, applyButton);
  root.append(intro, controls, statusBox, resultBox);
  container.replaceChildren(root);
}
