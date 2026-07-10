"""Serialize a forecast to netCDF + JSON metadata + a proof-of-life plot.

The netCDF follows the WindBorne gridded-forecast API naming/units
(https://api.windbornesystems.com/forecasts/version_1/gridded-forecast/) so
saved files match what their `/gridded` endpoint returns.
"""
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
LATS = np.arange(90, -90, -0.25)[:720].astype("float32")
LONS = np.arange(0, 360, 0.25).astype("float32")
API_LEVELS = [10, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400, 450, 500,
              550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000]

# WindBorne surface name -> (model varid, units)
SFC = {
    "temperature_2m": ("167_2t", "K"),
    "dewpoint_2m": ("168_2d", "K"),
    "pressure_msl": ("151_msl", "Pa"),
    "wind_u_10m": ("165_10u", "m/s"),
    "wind_v_10m": ("166_10v", "m/s"),
    "wind_u_100m": ("246_100u", "m/s"),
    "wind_v_100m": ("247_100v", "m/s"),
    "total_cloud_cover": ("45_tcc", "0-1"),
}
# WindBorne upper-level name -> (model varid, units)
UPPER = {
    "geopotential": ("129_z", "m2/s2"),
    "temperature": ("130_t", "K"),
    "wind_u": ("131_u", "m/s"),
    "wind_v": ("132_v", "m/s"),
    "specific_humidity": ("133_q", "kg/kg"),
}


def write_netcdf(real, era_mesh, meta, path):
    import xarray as xr

    fv = era_mesh.full_varlist

    def ch(name):
        return real[..., fv.index(name)].astype("float32")

    data = {}
    for out, (src, unit) in SFC.items():
        v = np.clip(ch(src), 0, 1) if out == "total_cloud_cover" else ch(src)
        data[out] = (("time", "lat", "lon"), v[None], {"units": unit})
    data["wind_speed_10m"] = (("time", "lat", "lon"),
                              np.sqrt(ch("165_10u") ** 2 + ch("166_10v") ** 2)[None], {"units": "m/s"})
    data["wind_speed_100m"] = (("time", "lat", "lon"),
                               np.sqrt(ch("246_100u") ** 2 + ch("247_100v") ** 2)[None], {"units": "m/s"})
    tp6 = np.clip((np.exp(ch("142_lsp-6h")) + np.exp(ch("143_cp-6h"))) * 1000.0, 0, 2000)
    data["total_precipitation_6h"] = (("time", "lat", "lon"), tp6[None], {"units": "mm"})

    for out, (src, unit) in UPPER.items():
        cube = np.stack([ch(f"{src}_{L}") for L in API_LEVELS], axis=0)
        data[out] = (("time", "level", "lat", "lon"), cube[None], {"units": unit})

    valid = np.datetime64(meta["valid_time"].replace("Z", ""))
    safe_attrs = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in meta.items()}
    safe_attrs.update({"Conventions": "CF-1.8", "institution": "reproduction of WindBorne WeatherMesh-3"})
    ds = xr.Dataset(
        data,
        coords={"time": [valid], "level": API_LEVELS, "lat": LATS, "lon": LONS},
        attrs=safe_attrs,
    )
    ds["level"].attrs = {"units": "hPa", "long_name": "pressure level"}
    ds["lat"].attrs = {"units": "degrees_north"}
    ds["lon"].attrs = {"units": "degrees_east"}
    enc = {v: {"zlib": True, "complevel": 4} for v in data}
    ds.to_netcdf(path, engine="netcdf4", encoding=enc)
    return path


def write_metadata(meta, path):
    Path(path).write_text(json.dumps(meta, indent=2, default=str))
    return path


def write_overview_plot(fields, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lm = np.load(REPO / "constants" / "additional_variables" / "land_mask.npy")
    lmx, lmy = np.linspace(0, 360, lm.shape[1]), np.linspace(90, -90, lm.shape[0])
    ext = [0, 360, -90, 90]

    def clim(a, lo=2, hi=98):
        return tuple(np.nanpercentile(np.asarray(a, np.float32), [lo, hi]))

    def panel(ax, f, title, cmap, vmin=None, vmax=None):
        if vmin is None:
            vmin, vmax = clim(f)
        im = ax.imshow(np.asarray(f, np.float32), extent=ext, origin="upper", aspect="auto",
                       cmap=cmap, vmin=vmin, vmax=vmax)
        ax.contour(lmx, lmy, lm, levels=[0.5], colors="k", linewidths=0.4)
        ax.set_title(title)
        plt.colorbar(im, ax=ax, shrink=0.8)

    jet = np.sqrt(fields["131_u_250"] ** 2 + fields["132_v_250"] ** 2)
    fig, ax = plt.subplots(2, 2, figsize=(15, 8))
    panel(ax[0, 0], fields["167_2t"] - 273.15, "2m temperature (degC)", "RdBu_r")
    panel(ax[0, 1], fields["151_msl"] / 100, "MSLP (hPa)", "viridis")
    panel(ax[1, 0], jet, "250 hPa wind speed (m/s)", "plasma", 0, clim(jet)[1])
    panel(ax[1, 1], fields["142_lsp"], "large-scale precip (mm)", "Blues", 0, clim(fields["142_lsp"], hi=99)[1])
    fig.tight_layout()
    fig.savefig(path, dpi=90)
    plt.close(fig)
    return path
