# splatgrade

**3D Gaussian Splat artifact quality gate.**

Inspect Gaussian PLY scenes for giant primitives, duplicates, low opacity, floaters, invalid ranges, and unstable bounds.

![splatgrade cover](demo/cover.png)

![splatgrade workbench](demo/dashboard.png)

## What ships

- Real ASCII PLY parser with standard log-scale and opacity handling
- Robust scene-center, median-scale, MAD floater, duplicate, bounds, and metadata checks
- Projected scene preview with flagged primitives
- CLI, JSON API, responsive workbench, Docker, tests, and CI

## Run it end to end

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e .
splatgrade demo
splatgrade scan point_cloud.ply
splatgrade serve
```

## Demo result

The 36-primitive fixture contains two giant splats, three duplicate pairs, four near-transparent primitives, and two distant floaters. The deterministic penalty model assigns quality 49 and grade D.

## Current basis

- [AAA-Gaussians, ICCV 2025](https://doi.org/10.1109/ICCV51701.2025.02567)
- [Perceptual Quality Assessment of 3D Gaussian Splatting](https://ojs.aaai.org/index.php/AAAI/article/download/37928/41890)

## Scope

Primitive-level preflight catches structural artifacts. Final perceptual quality still requires rendered multi-view inspection against capture references.

## Test

```bash
python -m unittest discover -s tests -v
```

MIT licensed.
