"""Load WeatherMesh-3 and run a forecast; de-normalize outputs to physical units."""
import os
import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
os.chdir(REPO)

FIELDS = {
    "167_2t": "167_2t", "151_msl": "151_msl", "165_10u": "165_10u", "166_10v": "166_10v",
    "129_z_500": "129_z_500", "130_t_850": "130_t_850",
    "131_u_250": "131_u_250", "132_v_250": "132_v_250", "133_q_850": "133_q_850",
    "142_lsp": "142_lsp",
}


def load_model(weights="model/WeatherMesh3.pt", device="cuda"):
    from model import get_WeatherMesh3
    return get_WeatherMesh3(weights).to(device).eval()


def run(model, gx, hx, t0_unix, era_mesh, lead_hours=6, device="cuda"):
    x = [gx[None].to(device), hx[None].to(device), torch.tensor([t0_unix], device=device)]
    with torch.no_grad():
        out = model(x, [lead_hours])
    pred = out[lead_hours][0]
    if pred.ndim == 4:
        pred = pred[0]
    real = pred.float().cpu().numpy() * era_mesh.normalization_matrix_std + era_mesh.normalization_matrix_mean

    fields = {}
    for name in FIELDS:
        v = real[..., era_mesh.full_varlist.index(name)]
        fields[name] = np.clip(np.exp(v) * 1000.0, 0, 2000) if name == "142_lsp" else v
    return real, fields, float(out["latent_l2"])
