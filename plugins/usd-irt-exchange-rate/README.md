# InvenTree USD / Iranian Toman Exchange Rate

A standalone [InvenTree](https://inventree.org/) currency exchange plugin for
USD and the Iranian toman (IRT). It supports:

- A manually configured IRT-per-USD rate, with no network access.
- An optional TGJU consumer which parses the live free-market USD rate using
  XPath and converts the quoted rial value to toman.
- Automatic updates every three hours through InvenTree's existing Django-Q2
  scheduler.
- Part, purchase-order, and Stock Item panels which show immutable USD and IRT
  pairs saved with each catalog, order-line, or physical-lot purchase price.
  They never reconvert saved prices using a later rate.
- IRT choices in every shared money field, including InvenTree's exceptional
  part-pricing override selectors which otherwise freeze their choices early.
- Immutable USD and IRT values, together with the applied rate, whenever a
  supported catalog, purchase-order, or Stock Item price is entered or changed.

No Celery worker, `django-constance`, API key, or modification to InvenTree's
source code is required.

## Requirements

- InvenTree 1.6.x
- Python 3.12 or newer
- InvenTree external plugin support and its background worker

## Installation

Install directly from this repository:

```bash
pip install "git+https://github.com/nooshin-shadiani/inventree-plugins.git@master#subdirectory=plugins/usd-irt-exchange-rate"
```

For a persistent InvenTree or Docker installation, add this line to
`plugins.txt` instead:

```text
git+https://github.com/nooshin-shadiani/inventree-plugins.git@master#subdirectory=plugins/usd-irt-exchange-rate
```

The package installs a lightweight Python startup hook so IRT is registered
before InvenTree builds currency choices. Restart both the InvenTree web server
and background worker after installation.
Then:

1. Enable **App Integration** in the InvenTree plugin settings.
2. Enable **URL Integration** and **User Interface Integration** so the dual
   currency panel and its read-only history endpoint are available.
3. Open the Admin Center, locate **Iranian Currency Exchange**, and activate it.
4. Apply the plugin database migration using the normal InvenTree update flow:

   ```bash
   invoke update
   ```

   For a Docker Compose installation, run:

   ```bash
   docker compose run --rm inventree-server invoke update
   ```

5. Restart the web server and background worker again.

Core prices remain saveable before the migration, but snapshots cannot be
recorded until the plugin table exists. Apply the migration before relying on
the history.

## Updating an existing installation

Back up the InvenTree database and media before upgrading. Update the plugin
reference to `master` (or, preferably, to an exact reviewed commit), install the
new package in the Python environment shared by both the web server and worker,
apply migrations, collect static files, and restart both processes.

For Docker deployments, do not run `pip install` only inside an existing server
container: that change is lost when the container is recreated and does not
update the worker. Rebuild the application image with the new plugin wheel, or
use an installer release which pins that plugin version, then run the normal
InvenTree migration and static-file steps before recreating server and worker.

## InvenTree configuration

Configure these system settings:

- **Default Currency**: `USD`
- **Supported Currencies**: `USD,IRT`
- **Currency Update Plugin**: `Iranian Currency Exchange`
- **Currency Update Interval**: `0`
- **Enable schedule integration**: enabled
- **Enable app integration**: enabled

Setting the core currency interval to zero prevents InvenTree's daily currency
task from overlapping the plugin's three-hour schedule. The plugin task forces
its selected update explicitly.

### Manual mode

Leave **Enable TGJU USD rate consumer** disabled and set **Manual USD to IRT
rate** to the number of Iranian tomans per one US dollar. The plugin makes no
TGJU request in this mode.

After changing the manual value, use **Refresh exchange rates** in Currency
Management to apply it immediately.

When upgrading from version 1.0, the plugin automatically converts the previous
manual IRR value to IRT until a new manual IRT value is saved.

### TGJU mode

Enable **Enable TGJU USD rate consumer**. Every three hours, the plugin asks
InvenTree to refresh the selected exchange provider and reads TGJU in this
order:

1. [`https://www.tgju.org/currency`](https://www.tgju.org/currency)
   - `string((//tr[@data-market-row='price_dollar_rl']/@data-price)[1])`
   - `string((//*[@id='l-price_dollar_rl']//*[contains(concat(' ', normalize-space(@class), ' '), ' info-price ')])[1])`
2. [`https://www.tgju.org/profile/price_dollar_rl`](https://www.tgju.org/profile/price_dollar_rl)
   - `string((//*[@data-target='profile-tour-current_rate']//*[@data-col='info.last_trade.PDrCotVal'])[1])`

TGJU publishes these values in Iranian rials. The plugin divides a valid quote
by ten and returns the result as IRT per USD.

If neither page provides a valid positive rate, the plugin returns no update;
it does not substitute the manual rate automatically.

## Historical price snapshots

When a non-empty supported catalog price is saved through the normal InvenTree
model path, the plugin reads the rate already applied in InvenTree's
`InvenTreeExchange` database backend. It does not contact TGJU and does not read
the manual setting during the price save. Each snapshot stores:

- The original amount and currency.
- The USD-to-IRT rate and its last successful update time.
- Locked USD and IRT equivalents.
- The source timestamp when available, capture timestamp, part ID, and source
  quantity.

Snapshots are captured for supplier, sale, and internal price breaks; the
minimum and maximum price overrides on a part; purchase-order line-item unit
prices; and each Stock Item's own `purchase_price`. Saving an unchanged price
does not create a duplicate. Quantity changes on a Stock Item also do not create
false price-history rows. Sequentially changing a non-empty price creates a new
row and never rewrites the older conversion. Clearing a nullable price does not
create a conversion row.

If no applied IRT rate exists, the original price is still recorded with a
`missing_rate` status and empty conversion fields. A later exchange-rate update
does not rewrite it using a rate which was unavailable when the price was
entered.

Administrators can inspect the append-only records under **USD / IRT Exchange
Rate > Price exchange snapshots** in the Django administration site. The plugin
disables adding, editing, and deleting these records through that interface.

Authorized users can open **Saved USD / IRT Prices** on any part, purchase
order, or Stock Item page. The part panel shows the latest snapshot for each
visible catalog price source: supplier, sale, internal, and manual override
prices. Purchase-order and Stock Item transaction prices are intentionally
excluded from the part panel and remain on their dedicated panels. The
purchase-order panel shows each line's item, quantity, entered unit price,
frozen USD and IRT unit values, applied rate, and capture time. The Stock Item
panel shows that physical lot's saved unit purchase price and its frozen USD/IRT
pair. It does not display a live-rate conversion, so later exchange-rate updates
cannot change the paired price shown there. Rows are filtered through the
requesting user's normal InvenTree model permissions.

Snapshot collection starts after App Integration is enabled, the plugin is
active, and its migrations are applied. The version 1.3.3 migration freezes
existing catalog prices using the rate applied at upgrade time. Version 1.4.0
does the same once for existing purchase-order line prices, and version 1.5.0
backfills existing Stock Item purchase prices. These migrations cannot
reconstruct a historical entry-time rate; the captured timestamp identifies
when each backfill was frozen. Future price saves always use the rate applied at
the exact time of that save.

The standard InvenTree UI, API serializers, and spreadsheet importer use normal
model saves and are covered. Direct `bulk_create`, `bulk_update`, raw SQL, and
`QuerySet.update` calls made by custom code bypass Django signals and therefore
do not create snapshots.

If multiple writers update the same source price concurrently, delayed signal
handlers refresh from the locked source row so an older value cannot become the
latest snapshot. Distinct overlapping writes can therefore coalesce to the
latest committed value; this table is an append-only price history, not a
database change-data-capture stream.

## Development

From the repository root, enter this plugin directory and install its
development tools into an InvenTree development environment:

```bash
cd plugins/usd-irt-exchange-rate
python -m pip install --editable ".[dev]"
```

The behavior tests run through InvenTree's Django test runner. From the plugin
directory, point the command at an InvenTree checkout:

```bash
INVENTREE_PLUGINS_ENABLED=true \
INVENTREE_PLUGIN_TESTING=true \
INVENTREE_PLUGIN_TESTING_SETUP=true \
PYTHONPATH="$PWD" \
python /path/to/InvenTree/src/backend/InvenTree/manage.py test tests --keepdb
```

From the plugin directory, run the type checker:

```bash
pyrefly check
```

Build and inspect the distributable package from the same directory with:

```bash
python -m build
python -m twine check dist/*
```
