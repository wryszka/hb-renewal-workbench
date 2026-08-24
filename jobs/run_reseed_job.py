"""Demo reset — reseed the schema to the pristine demo state.

Triggered by the app's "Reset demo" button (jobs.run_now). Runs on serverless
under the job's own identity (ambient auth). Regenerates the synthetic demo files
to a writable dir, then reseeds via the same scripts as `deploy.sh`:
make_carrier_file -> seed_book (build_schema, ingest hero, historical + governance)
-> generate_reviewer. Leaves 54 docs / 49 scenarios / 5 findings. All synthetic.

Serverless notes: `spark_python_task` execs this file WITHOUT defining __file__,
so we avoid it here (runpy sets __file__ for each script it runs). The Workspace
files tree is read-only, so demo files are written to /tmp via HB_DEMO_DIR.
"""
import os, sys, runpy, pathlib

# Bundle files root (matches databricks.yml root_path + /files); fall back to cwd.
ROOT = pathlib.Path("/Workspace/Shared/.bundle/hb-renewal-workbench/files")
if not (ROOT / "data").exists():
    ROOT = pathlib.Path(os.getcwd())

os.environ["HB_DEMO_DIR"] = "/tmp/hb_demo"   # writable dir for regenerated .xlsx
os.environ.pop("HB_PROFILE", None)           # ambient auth on the Job
for p in ("data", "app", "jobs"):
    sys.path.insert(0, str(ROOT / p))

for rel in ("data/make_carrier_file.py", "data/seed_book.py", "data/generate_reviewer.py",
            "data/stage_demo_files.py"):
    print(f"== reseed step: {rel} ==", flush=True)
    runpy.run_path(str(ROOT / rel), run_name="__main__")

print("reseed complete — demo restored to clean state.", flush=True)
