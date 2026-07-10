"""Serialize a forecast to netCDF + JSON metadata + a proof-of-life plot."""
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
LATS = np.arange(90, -90, -0.25)[:720]
LONS = np.arange(0, 360, 0.25)

_NC_VARS = {
    "t2m": ("167_2t", "K", "2 metre temperature"),
    "mslp": ("151_msl", "Pa", "mean sea level pressure"),
    "u10": ("165_10u", "m s-1", "10 metre U wind"),
    "v10": ("166_10v", "m s-1", "10 metre V wind"),
    "z500": ("129_z_500", "m2 s-2", "500 hPa geopotential"),
    "t850": ("130_t_850", "K", "850 hPa temperature"),
    "precip_lsp": ("142_lsp", "mm", "large-scale precipitation"),
}


def write_netcdf(fields, meta, path):
    import xarray as xr
    ds = xr.Dataset(
        {name: (("lat", "lon"), fields[src].astype("float32"), {"units": u, "long_name": ln})
         for name, (src, u, ln) in _NC_VARS.items()},
        coords={"lat": LATS.astype("float32"), "lon": LONS.astype("float32")},
        attrs=meta,
    )
    ds.to_netcdf(path, engine="netcdf4")
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
