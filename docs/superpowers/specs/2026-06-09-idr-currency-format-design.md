# Indonesian Currency (IDR) Format Design

## Goal
Configure Apache Superset to use Indonesian conventions for number and currency formatting globally. Specifically, use dot (`.`) as the thousands separator, comma (`,`) as the decimal separator, and `Rp. ` as the default currency prefix.

## Proposed Changes
We will modify the `superset_config.py` file to introduce the `D3_FORMAT` configuration.

### `superset_config.py`
Add the following `D3_FORMAT` override:
```python
D3_FORMAT = {
    "decimal": ",",
    "thousands": ".",
    "grouping": [3],
    "currency": ["Rp. ", ""]
}
```

This configuration intercepts the default D3 formatting engine (which powers Superset visualizations) and overrides the US locale defaults with Indonesian locale standards.

## Verification
1. Restart the Superset containers to apply the configuration change.
2. View any dashboard chart with a number formatted as currency (e.g., `$,.2f`).
3. Verify that the value `1000000` is displayed as `Rp. 1.000.000,00`.
