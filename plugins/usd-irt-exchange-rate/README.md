# InvenTree USD / Iranian Toman Exchange Rate

A standalone [InvenTree](https://inventree.org/) currency exchange plugin for
USD and the Iranian toman (IRT). It supports:

- A manually configured IRT-per-USD rate, with no network access.
- An optional TGJU consumer which parses the live free-market USD rate using
  XPath and converts the quoted rial value to toman.
- Automatic updates every three hours through InvenTree's existing Django-Q2
  scheduler.

No Celery worker, `django-constance`, API key, or modification to InvenTree's
source code is required.

## Requirements

- InvenTree 1.6.0 or newer
- Python 3.12 or newer
- InvenTree external plugin support and its background worker

## Installation

Install directly from this repository:

```bash
pip install "git+https://github.com/nooshin-shadiani/inventree-plugins.git@main#subdirectory=plugins/usd-irt-exchange-rate"
```

For a persistent InvenTree or Docker installation, add this line to
`plugins.txt` instead:

```text
git+https://github.com/nooshin-shadiani/inventree-plugins.git@main#subdirectory=plugins/usd-irt-exchange-rate
```

Restart both the InvenTree web server and background worker after installation.
Then open the Admin Center, locate **Iranian Currency Exchange**, and activate
it.

## InvenTree configuration

Configure these system settings:

- **Default Currency**: `USD`
- **Supported Currencies**: `USD,IRT`
- **Currency Update Plugin**: `Iranian Currency Exchange`
- **Currency Update Interval**: `0`
- **Enable schedule integration**: enabled

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
PYTHONPATH="$PWD" python /path/to/InvenTree/src/backend/InvenTree/manage.py test tests.test_plugin --keepdb
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
