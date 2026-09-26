"""OCR_ENGINE_MODE wiring: how the provider chain gets constructed."""
import logging

from app.ocr_provider import (
    RapidOCRProvider,
    TesseractProvider,
    _build_provider_chain,
    get_provider_chain,
)


def test_auto_chain_is_rapidocr_then_tesseract():
    """mode="auto" keeps today's behavior: RapidOCR primary, Tesseract fallback."""
    chain = _build_provider_chain("auto")
    assert len(chain) == 2
    assert isinstance(chain[0], RapidOCRProvider)
    assert isinstance(chain[1], TesseractProvider)


def test_tesseract_only_chain_has_no_rapidocr():
    """mode="tesseract_only" constructs exactly one provider: Tesseract."""
    chain = _build_provider_chain("tesseract_only")
    assert len(chain) == 1
    assert isinstance(chain[0], TesseractProvider)
    assert not any(isinstance(p, RapidOCRProvider) for p in chain)


def test_unknown_mode_falls_back_to_auto_with_warning():
    """An unrecognized mode logs a WARNING and builds the "auto" chain.

    The app.* logger hierarchy has propagate=False (set by
    configure_app_logging), so caplog via the root logger can't see the
    record reliably — attach a temporary Handler directly to the logger.
    """
    log = logging.getLogger("app.ocr_provider")
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture()
    old_level = log.level
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        chain = _build_provider_chain("definitely_not_a_mode")
    finally:
        log.removeHandler(handler)
        log.setLevel(old_level)

    assert isinstance(chain[0], RapidOCRProvider)
    assert isinstance(chain[1], TesseractProvider)
    assert any(
        r.levelno == logging.WARNING and "definitely_not_a_mode" in r.getMessage()
        for r in records
    ), "unknown mode must emit a WARNING on app.ocr_provider"


def test_get_provider_chain_returns_the_module_level_chain():
    """get_provider_chain() is the same object as the import-time _PROVIDER_CHAIN."""
    import app.ocr_provider as ocr_provider

    assert get_provider_chain() is ocr_provider._PROVIDER_CHAIN
