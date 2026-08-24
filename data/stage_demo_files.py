#!/usr/bin/env python3
"""Stage the synthetic demo carrier files into the UC Volume so anyone running the
demo can download them (Catalog Explorer or CLI) WITHOUT cloning the repo.

Uploads to /Volumes/{cat}/{sch}/landing/demo_files/. Regenerates the files first
(via make_carrier_file) if they are not already present in the source dir. All
synthetic — invented carrier/employer, no real data.

Run: uv run --native-tls --with databricks-sdk --with openpyxl data/stage_demo_files.py
"""
from __future__ import annotations
import os, io, runpy, pathlib
from databricks.sdk import WorkspaceClient

CAT = os.getenv("HB_CATALOG", "lr_dev_aws_us_catalog")
SCH = os.getenv("HB_SCHEMA", "hb_renewal")
DEST = f"/Volumes/{CAT}/{SCH}/landing/demo_files"
HERE = pathlib.Path(__file__).resolve().parent
SRC = pathlib.Path(os.getenv("HB_DEMO_DIR") or HERE)
FILES = ["meridian_harborview_2026H2.xlsx", "meridian_brokenlayout.xlsx",
         "meridian_harborview_2026H2_v2.xlsx", "meridian_harborview_2026H2_month13.xlsx"]
w = WorkspaceClient(profile=os.getenv("HB_PROFILE") or None)

# regenerate into SRC if any are missing (serverless-safe: runpy sets __file__)
if not all((SRC / f).exists() for f in FILES):
    os.environ["HB_DEMO_DIR"] = str(SRC)
    runpy.run_path(str(HERE / "make_carrier_file.py"), run_name="__main__")

for f in FILES:
    data = (SRC / f).read_bytes()
    w.files.upload(f"{DEST}/{f}", io.BytesIO(data), overwrite=True)
    print(f"  staged {f} -> {DEST}/{f} ({len(data)} bytes)")
print(f"demo files staged in Volume: {DEST}/")
