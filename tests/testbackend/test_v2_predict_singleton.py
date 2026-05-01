"""Regression test: _load_model_and_config must cache by model_dir.

If anyone removes the @lru_cache decorator on _load_model_and_config,
each prediction call will re-deserialize a multi-MB joblib pickle. On a
512 MB Render dyno running multiple concurrent evaluations, that thrash
is the difference between "fits" and "OOM-kills the worker." This test
guards against silently undoing the cache.
"""

from __future__ import annotations

import os

from backend.ml.models import v2_predict


def _real_model_dir() -> str:
    """One real model dir we know exists in the repo."""
    return os.path.join(
        os.path.dirname(v2_predict.__file__),
        "models_inf",
        "models_d1_or_not_inf",
        "version_04212026",
    )


def test_load_model_returns_same_object_on_repeat_call():
    # Clear the cache so this test is hermetic regardless of order.
    v2_predict._load_model_and_config.cache_clear()

    model_dir = _real_model_dir()
    first_model, first_config = v2_predict._load_model_and_config(model_dir)
    second_model, second_config = v2_predict._load_model_and_config(model_dir)

    # Identity, not equality — confirms the cache returned the same object
    # rather than re-loading a fresh equivalent one.
    assert first_model is second_model
    assert first_config is second_config

    # And the lru_cache should report exactly one miss + one hit.
    info = v2_predict._load_model_and_config.cache_info()
    assert info.hits >= 1
    assert info.misses == 1


def test_load_model_caches_per_model_dir():
    """Two distinct model_dirs should each load once and stay cached."""
    v2_predict._load_model_and_config.cache_clear()

    inf_dir = _real_model_dir()
    of_dir = os.path.join(
        os.path.dirname(v2_predict.__file__),
        "models_of",
        "models_d1_or_not_of",
        "version_04202026",
    )

    inf_model, _ = v2_predict._load_model_and_config(inf_dir)
    of_model, _ = v2_predict._load_model_and_config(of_dir)

    # Different dirs → different cached objects.
    assert inf_model is not of_model

    # Repeated calls return the same cached objects.
    assert v2_predict._load_model_and_config(inf_dir)[0] is inf_model
    assert v2_predict._load_model_and_config(of_dir)[0] is of_model

    info = v2_predict._load_model_and_config.cache_info()
    assert info.misses == 2
    assert info.hits >= 2
