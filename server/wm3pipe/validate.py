"""Physical-plausibility checks on a forecast; returns a metrics dict + validity."""
import numpy as np


def validate(fields):
    t2c = fields["167_2t"] - 273.15
    mslp = fields["151_msl"] / 100.0
    wind10 = np.sqrt(fields["165_10u"] ** 2 + fields["166_10v"] ** 2)
    jet250 = np.sqrt(fields["131_u_250"] ** 2 + fields["132_v_250"] ** 2)

    nan_count = int(sum(int(np.isnan(v).sum()) for v in fields.values()))
    m = {
        "t2m_min_C": float(np.nanmin(t2c)), "t2m_max_C": float(np.nanmax(t2c)),
        "t2m_mean_C": float(np.nanmean(t2c)),
        "mslp_min_hPa": float(np.nanmin(mslp)), "mslp_max_hPa": float(np.nanmax(mslp)),
        "wind10_max_ms": float(np.nanmax(wind10)), "jet250_max_ms": float(np.nanmax(jet250)),
        "precip_max_mm": float(np.nanmax(fields["142_lsp"])), "nan_count": nan_count,
    }
    # bounds a physically plausible global field must satisfy
    m["valid"] = bool(
        nan_count == 0
        and -95 < m["t2m_min_C"] and m["t2m_max_C"] < 65
        and 850 < m["mslp_min_hPa"] and m["mslp_max_hPa"] < 1095
        and m["wind10_max_ms"] < 150 and 30 < m["jet250_max_ms"] < 200
    )
    return m
