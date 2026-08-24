"""Ingestion Job task — scan the Volume inbox, process each file through the
ingestion pipeline, and move it to processed/ or quarantine/.

Runs on serverless (spark_python_task). Triggered by file-arrival on the inbox.
Shares the exact code path as the local seed via ingest_pipeline.process_file.
"""
from __future__ import annotations
import os
from databricks.sdk import WorkspaceClient
import ingest_pipeline  # same directory, on sys.path for spark_python_task

CAT = os.getenv("HB_CATALOG", "lr_dev_aws_us_catalog")
SCH = os.getenv("HB_SCHEMA", "hb_renewal")
BASE = f"/Volumes/{CAT}/{SCH}/landing"
w = WorkspaceClient()


def main():
    try:
        entries = list(w.files.list_directory_contents(f"{BASE}/inbox"))
    except Exception as e:
        print(f"inbox unavailable: {e}")
        return
    for e in entries:
        if not e.path.endswith(".xlsx"):
            continue
        local = f"/tmp/{os.path.basename(e.path)}"
        with open(local, "wb") as fh:
            fh.write(w.files.download(e.path).contents.read())
        res = ingest_pipeline.process_file(local, actor="ingest-job")
        # the pipeline archives the original into processed/ or quarantine/ keyed by
        # doc_id (res["stored_path"]); we only clear the inbox copy here.
        print(f"{os.path.basename(e.path)} -> {res.get('status')} {res.get('doc_id','')} -> {res.get('stored_path','(not archived)')}")
        try:
            w.files.delete(e.path)
        except Exception as ex:
            print(f"  (could not clear inbox copy: {ex})")


if __name__ == "__main__":
    main()
