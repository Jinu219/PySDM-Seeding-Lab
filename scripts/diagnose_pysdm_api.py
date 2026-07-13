from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    try:
        import PySDM
        print("PySDM:", getattr(PySDM, "__version__", "unknown"), getattr(PySDM, "__file__", "unknown"))
    except Exception as exc:
        print("PySDM import failed:", repr(exc))

    try:
        import PySDM_examples
        print(
            "PySDM_examples:",
            getattr(PySDM_examples, "__version__", "unknown"),
            getattr(PySDM_examples, "__file__", "unknown"),
        )
    except Exception as exc:
        print("PySDM_examples import failed:", repr(exc))

    try:
        from PySDM.initialisation.sampling.spectral_sampling import ConstantMultiplicity
        from PySDM.initialisation.spectra import Lognormal

        sampler = ConstantMultiplicity(Lognormal(norm_factor=1.0, m_mode=1.0, s_geom=1.1))
        public = [name for name in dir(sampler) if not name.startswith("_")]
        print("ConstantMultiplicity public methods/attrs:")
        for name in public:
            print(" -", name)
    except Exception as exc:
        print("ConstantMultiplicity inspection failed:", repr(exc))


if __name__ == "__main__":
    main()
