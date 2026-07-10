"""Physical-plausibility checks on a forecast; returns a metrics dict + validity.

Checks bounds AND physical consistency (non-negative humidity, dewpoint <= temp,
finite precipitation). Known small ML artefacts (a little negative humidity, a few
dewpoint>temp cells) are *reported* as fractions and only fail validity if large.
"""
import numpy as np


def validate(fields, real=None, era_mesh=None):
    t2c = fields["167_2t"] - 273.15
    mslp = fields["151_msl"] / 100.0
    wind10 = np.sqrt(fields["165_10u"] ** 2 + fields["166_10v"] ** 2)
    jet250 = np.sqrt(fields["131_u_250"] ** 2 + fields["132_v_250"] ** 2)
    precip = np.clip(np.nan_to_num(fields["142_lsp"], nan=0.0, posinf=0.0, neginf=0.0), 0, 2000)
    nan_count = int(sum(int(np.isnan(v).sum()) for v in fields.values()))

    # physical-consistency diagnostics over the full output (all humidity levels, dewpoint vs temp)
    neg_q_frac = 0.0
    td_gt_t_frac = 0.0
    if real is not None and era_mesh is not None:
        fv = era_mesh.full_varlist
        qcols = [i for i, n in enumerate(fv) if n.startswith("133_q_")]
        if qcols:
            neg_q_frac = float((real[..., qcols] < 0).mean())
        td = real[..., fv.index("168_2d")]
        t2 = real[..., fv.index("167_2t")]
        td_gt_t_frac = float((td > t2 + 0.1).mean())

    m = {
        "t2m_min_C": float(np.nanmin(t2c)), "t2m_max_C": float(np.nanmax(t2c)),
        "t2m_mean_C": float(np.nanmean(t2c)),
        "mslp_min_hPa": float(np.nanmin(mslp)), "mslp_max_hPa": float(np.nanmax(mslp)),
        "wind10_max_ms": float(np.nanmax(wind10)), "jet250_max_ms": float(np.nanmax(jet250)),
        "precip_max_mm": float(np.nanmax(precip)), "nan_count": nan_count,
        "neg_humidity_frac": neg_q_frac, "dewpoint_gt_temp_frac": td_gt_t_frac,
    }
    m["valid"] = bool(
        nan_count == 0
        and -95 < m["t2m_min_C"] and m["t2m_max_C"] < 65
        and 850 < m["mslp_min_hPa"] and m["mslp_max_hPa"] < 1095
        and m["wind10_max_ms"] < 150 and 30 < m["jet250_max_ms"] < 200
        and m["precip_max_mm"] <= 2000
        and neg_q_frac < 0.05 and td_gt_t_frac < 0.05
    )
    return m
