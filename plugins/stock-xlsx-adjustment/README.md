# InvenTree Stock XLSX Adjustment

A standalone InvenTree plugin for previewing and applying bulk stock movements
from an Excel workbook. It adds a panel to the root **Stock Locations** page and
supports logged, user-attributed `add`, `remove`, and `count` operations without
changing InvenTree core.

## Input format

Download the template from the plugin panel, or create an `.xlsx` workbook with
these columns:

| Column | Required | Meaning |
| --- | --- | --- |
| `stock_item_id` | Yes | Exact InvenTree stock-item / lot ID. |
| `operation` | Yes | `add`, `remove`, or `count`. |
| `quantity` | Yes | Positive delta for add/remove; non-negative absolute value for count. |
| `notes` | No | Audit note stored on the stock tracking entry, up to 512 characters. |

Example:

| stock_item_id | operation | quantity | notes |
| ---: | --- | ---: | --- |
| 42 | add | 10 | Received into stock |
| 51 | remove | 3 | Damaged components |
| 63 | count | 25 | Physical stocktake |

The preview checks the entire workbook and shows the current and resulting
quantity for each row. Applying is all-or-nothing: affected stock rows are
locked in stable ID order, every row is revalidated, and any error prevents all
changes. Successful rows use InvenTree's normal stock methods, so stock history
records the operation, quantity delta, notes, time, and requesting user.

For safety, the plugin rejects duplicate stock-item IDs, missing stock items,
add/remove operations on serialized stock, serialized counts other than one,
and removals larger than the available quantity. The normal InvenTree importer
remains available for creating records or setting absolute values; this plugin
is specifically for audited stock movements.

## Requirements

- InvenTree 1.6.x
- Python 3.12 or newer
- InvenTree plugin, plugin URL, and plugin user-interface support
- A user with **Stock Item > Change** and **Stock Location > View** permissions
- OAuth clients also need the stock-change scope (`r:change:stock`)

The parser uses the XLSX support already installed with InvenTree. It follows
InvenTree's importer limits: at most 32 MiB, 5,000 rows, and 1,000 columns.

## Installation

Install directly from this repository:

```bash
pip install "git+https://github.com/nooshin-shadiani/inventree-plugins.git@main#subdirectory=plugins/stock-xlsx-adjustment"
```

For a persistent InvenTree or Docker installation, add the same URL to
`plugins.txt`, then restart the InvenTree server and worker.

In the Admin Center:

1. Enable external plugins.
2. Enable **URL Integration** and **User Interface Integration**.
3. Locate **Stock XLSX Adjustment** and activate it.
4. Restart the server so the plugin URLs and static panel file are available.

Users with both required permissions can then open **Stock XLSX Adjustment**
from the top navigation or from the plugin-provided panel under
**Stock Locations**. No App Integration, migration, Celery worker, or plugin
database table is required.

## Development

From this plugin directory, install its development tool and run the checks:

```bash
python -m pip install --editable ".[dev]"
ruff check .
ruff format --check .
pyrefly check
python -m build
python -m twine check dist/*
```

This plugin is released under the MIT License.
