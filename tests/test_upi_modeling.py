import pandas as pd

from src.models.upi import (
    UPI_HIGH_RISK_PROXY_COLUMNS,
    UPI_STABLE_TRANSACTION_COLUMNS,
    fit_upi_builder,
)


def test_upi_builder_uses_only_stable_transaction_columns():
    df = pd.DataFrame(
        {
            "TARGET": [0, 1, 0, 1],
            "SK_ID_CURR": [1, 2, 3, 4],
            "AMT_INCOME_TOTAL": [100000, 120000, 90000, 110000],
            **{col: [1.0, 2.0, 3.0, 4.0] for col in UPI_STABLE_TRANSACTION_COLUMNS},
            **{col: [0.0, 10.0, 0.0, 10.0] for col in UPI_HIGH_RISK_PROXY_COLUMNS},
        }
    )

    builder = fit_upi_builder(df)

    assert set(builder.raw_columns_) == set(UPI_STABLE_TRANSACTION_COLUMNS)
    assert "AMT_INCOME_TOTAL" not in builder.raw_columns_
    assert not set(UPI_HIGH_RISK_PROXY_COLUMNS).intersection(builder.raw_columns_)
    assert set(UPI_HIGH_RISK_PROXY_COLUMNS).issubset(builder.excluded_raw_columns_)
