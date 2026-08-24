"""Sweep the live DEV state of the H&B rebuild — ground truth for the corpus."""
from databricks.sdk import WorkspaceClient
WAREHOUSE = "a3b61648ea4809e3"
CAT, SCH = "lr_dev_aws_us_catalog", "hb_renewal"
w = WorkspaceClient(profile="DEV")

def q(sql):
    r = w.statement_execution.execute_statement(warehouse_id=WAREHOUSE, statement=sql, wait_timeout="50s")
    if not r.status or r.status.state.value != "SUCCEEDED":
        return [["ERR", (r.status.error.message if r.status and r.status.error else "?")]]
    return r.result.data_array or []

print("### TABLES & VIEWS in", f"{CAT}.{SCH}")
for row in q(f"SHOW TABLES IN {CAT}.{SCH}"):
    name = row[1]
    kind = "view" if name.startswith("6_") else "table"
    cnt = q(f"SELECT count(*) FROM {CAT}.{SCH}.`{name}`")
    print(f"  {name:<24} {cnt[0][0]}")

print("\n### UC FUNCTIONS")
for row in q(f"""SELECT routine_name, data_type
                 FROM system.information_schema.routines
                 WHERE specific_catalog='{CAT}' AND routine_schema='{SCH}'"""):
    print(f"  {row[0]}() -> {row[1]}")

print("\n### COLUMNS per table")
for row in q(f"SHOW TABLES IN {CAT}.{SCH}"):
    name = row[1]
    cols = q(f"SELECT column_name, data_type FROM system.information_schema.columns "
             f"WHERE table_catalog='{CAT}' AND table_schema='{SCH}' AND table_name='{name}' ORDER BY ordinal_position")
    print(f"  {name}: " + ", ".join(f"{c[0]}" for c in cols))

print("\n### BENCHMARK VIEW sample (derived book trend)")
for row in q(f"SELECT carrier, group_band, renewals_negotiated, book_trend_median, avg_carrier_action, avg_negotiated_action FROM {CAT}.{SCH}.`6_book_trend_benchmark` ORDER BY carrier, group_band LIMIT 6"):
    print("  ", row)

print("\n### DELTA HISTORY (versioning proof) — 5_scenario")
for row in q(f"DESCRIBE HISTORY {CAT}.{SCH}.`5_scenario`")[:3]:
    print("  v", row[0], row[1], row[3])
