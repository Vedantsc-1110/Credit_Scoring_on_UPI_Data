# MasterMind model training package

_UPI_EXPORTS = {
    "UPI_DATASET_PATH",
    "build_upi",
    "fit_upi_builder",
    "load_upi_artifacts",
    "score_upi_frame",
    "score_upi_record",
    "train_upi_model",
}

__all__ = sorted(_UPI_EXPORTS)


def __getattr__(name):
    if name in _UPI_EXPORTS:
        from src.models import upi

        return getattr(upi, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
