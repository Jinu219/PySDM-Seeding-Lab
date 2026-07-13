import numpy as np
import pandas as pd


def lognormal_distribution(radius_m: np.ndarray, number_concentration: float, mean_radius_m: float, sigma_g: float) -> pd.DataFrame:
    distribution = number_concentration / (np.sqrt(2 * np.pi) * np.log(sigma_g)) * np.exp(
        -((np.log(radius_m) - np.log(mean_radius_m)) ** 2) / (2 * np.log(sigma_g) ** 2)
    )

    return pd.DataFrame(
        {
            "radius_m": radius_m,
            "dN_dlnr": distribution,
        }
    )
