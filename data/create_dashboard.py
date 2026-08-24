#!/usr/bin/env python3
"""Create/update + publish the 'HB Renewal Book' AI/BI (Lakeview) dashboard, embedded in the app.

Built for a renewal-desk lead: headline KPIs (renewals, carrier ask vs negotiated, value
negotiated), the negotiation story (ask vs negotiated by carrier), who runs rich (book trend +
padder flag), the book mix, and the claims trend. Themed palette (not all blue) + an in-dashboard
"Ask Genie" button wired to the same governed book.

Usage: python3 data/create_dashboard.py [profile] [warehouse] [catalog] [schema] [dashboard_id]
"""
import json, pathlib, sys
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import Dashboard

prof = sys.argv[1] if len(sys.argv) > 1 else "DEV"
wh = sys.argv[2] if len(sys.argv) > 2 else "a3b61648ea4809e3"
cat = sys.argv[3] if len(sys.argv) > 3 else "lr_dev_aws_us_catalog"
sch = sys.argv[4] if len(sys.argv) > 4 else "hb_renewal"
existing = sys.argv[5] if len(sys.argv) > 5 else None
F = f"`{cat}`.`{sch}`"
_idf = pathlib.Path(__file__).with_name("genie_space_id.txt")
GENIE_SPACE = _idf.read_text().strip() if _idf.exists() else "01f19d63fe03198a95c55b64a81ea535"

DATASETS = [
    {"name": "ds_bench", "displayName": "By carrier",
     "queryLines": [
        f"SELECT carrier, round(avg(book_trend_median),4) book_trend, round(avg(avg_carrier_action),4) carrier_action, ",
        f"round(avg(avg_negotiated_action),4) negotiated_action, round(avg(avg_negotiation_delta),4) delta, ",
        f"round(sum(total_value_negotiated),0) value_negotiated, sum(renewals_negotiated) renewals, ",
        f"CASE WHEN avg(book_trend_median)>=0.075 THEN 'Padder (rich)' WHEN avg(book_trend_median)<=0.06 THEN 'Fair' ELSE 'Mid' END flag ",
        f"FROM {F}.`6_book_trend_benchmark` GROUP BY carrier ORDER BY carrier_action DESC "]},
    {"name": "ds_action", "displayName": "Ask vs negotiated",
     "queryLines": [
        f"SELECT carrier, 'Carrier ask' series, round(avg(avg_carrier_action),4) action FROM {F}.`6_book_trend_benchmark` GROUP BY carrier ",
        f"UNION ALL ",
        f"SELECT carrier, 'Our negotiated' series, round(avg(avg_negotiated_action),4) action FROM {F}.`6_book_trend_benchmark` GROUP BY carrier "]},
    {"name": "ds_band", "displayName": "By group band",
     "queryLines": [
        f"SELECT group_band, round(avg(avg_carrier_action),4) carrier_action, round(avg(avg_negotiated_action),4) negotiated_action, ",
        f"sum(renewals_negotiated) renewals FROM {F}.`6_book_trend_benchmark` GROUP BY group_band ORDER BY group_band "]},
    {"name": "ds_claims", "displayName": "Claims experience",
     "queryLines": [
        f"SELECT to_date(concat('01-',month),'dd-MMM-yyyy') month_date, round(sum(total_incurred),0) total_incurred, round(avg(pmpm),2) pmpm ",
        f"FROM {F}.`mv_claims_experience` GROUP BY month ORDER BY month_date "]},
]

PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
USD = {"type": "number-currency", "currencyCode": "USD", "abbreviation": "compact", "decimalPlaces": {"type": "max", "places": 1}}
NUM = {"type": "number", "decimalPlaces": {"type": "exact", "places": 0}}


def txt(name, md, w=12, h=1, x=0, y=0):
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": [md]}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def counter(name, ds, fname, expr, title, fmt, w=3, h=3, x=0, y=0):
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
              "datasetName": ds, "fields": [{"name": fname, "expression": expr}], "disaggregated": False}}],
            "spec": {"version": 2, "widgetType": "counter",
                     "encodings": {"value": {"fieldName": fname, "displayName": title, "format": fmt}},
                     "frame": {"showTitle": True, "title": title}}},
            "position": {"x": x, "y": y, "width": w, "height": h}}


def bar(name, ds, x, y, title, color=None, mappings=None, group=False, wtype="bar",
        w=6, h=6, x0=0, y0=0, yfmt=None, scale="categorical"):
    fields = [{"name": x, "expression": f"`{x}`"}, {"name": y, "expression": f"`{y}`"}]
    ycfg = {"fieldName": y, "scale": {"type": "quantitative"}}
    if yfmt:
        ycfg["format"] = yfmt
    enc = {"x": {"fieldName": x, "scale": {"type": scale}}, "y": ycfg}
    if color:
        fields.append({"name": color, "expression": f"`{color}`"})
        cs = {"type": "categorical"}
        if mappings:
            cs["mappings"] = mappings
        enc["color"] = {"fieldName": color, "scale": cs}
    spec = {"version": 3, "widgetType": wtype, "encodings": enc, "frame": {"title": title, "showTitle": True}}
    if group:
        spec["mark"] = {"layout": "group"}
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
              "datasetName": ds, "fields": fields, "disaggregated": True}}], "spec": spec},
            "position": {"x": x0, "y": y0, "width": w, "height": h}}


def pie(name, ds, angle, color, title, w=4, h=6, x0=0, y0=0):
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
              "datasetName": ds, "fields": [{"name": angle, "expression": f"`{angle}`"},
                                            {"name": color, "expression": f"`{color}`"}], "disaggregated": True}}],
            "spec": {"version": 3, "widgetType": "pie",
                     "encodings": {"angle": {"fieldName": angle, "scale": {"type": "quantitative"}},
                                   "color": {"fieldName": color, "scale": {"type": "categorical"}},
                                   "label": {"show": True}},
                     "frame": {"title": title, "showTitle": True}}},
            "position": {"x": x0, "y": y0, "width": w, "height": h}}


ASK_MAP = [{"value": "Carrier ask", "color": "#E69F00"}, {"value": "Our negotiated", "color": "#009E73"}]
FLAG_MAP = [{"value": "Padder (rich)", "color": "#D55E00"}, {"value": "Fair", "color": "#009E73"}, {"value": "Mid", "color": "#56B4E9"}]

layout = [
    txt("t_title", "## Renewal book — carrier ask vs the position we negotiated", 12, 1, 0, 0),
    txt("t_sub", "Every retained decision, rolled up. All figures synthetic.", 12, 1, 0, 1),
    counter("k_renewals", "ds_bench", "sum(renewals)", "SUM(`renewals`)", "Renewals negotiated", NUM, 3, 3, 0, 2),
    counter("k_ask", "ds_bench", "avg(carrier_action)", "AVG(`carrier_action`)", "Avg carrier ask", PCT, 3, 3, 3, 2),
    counter("k_neg", "ds_bench", "avg(negotiated_action)", "AVG(`negotiated_action`)", "Avg negotiated", PCT, 3, 3, 6, 2),
    counter("k_value", "ds_bench", "sum(value_negotiated)", "SUM(`value_negotiated`)", "Value negotiated / yr", USD, 3, 3, 9, 2),
    txt("t_neg", "### Negotiation by carrier", 12, 1, 0, 5),
    bar("w_ask", "ds_action", "carrier", "action", "Carrier ask vs our negotiated position", color="series",
        mappings=ASK_MAP, group=True, w=6, h=6, x0=0, y0=6, yfmt=PCT),
    bar("w_value", "ds_bench", "carrier", "value_negotiated", "Value negotiated by carrier ($/yr)", color="carrier",
        w=6, h=6, x0=6, y0=6, yfmt=USD),
    txt("t_book", "### Who runs rich · book mix", 12, 1, 0, 12),
    bar("w_trend", "ds_bench", "carrier", "book_trend", "Book trend by carrier (padder = rich)", color="flag",
        mappings=FLAG_MAP, w=4, h=6, x0=0, y0=13, yfmt=PCT),
    bar("w_band", "ds_band", "group_band", "carrier_action", "Carrier action by group-size band", color="group_band",
        w=4, h=6, x0=4, y0=13, yfmt=PCT),
    pie("w_mix", "ds_band", "renewals", "group_band", "Renewals by group-size band", w=4, h=6, x0=8, y0=13),
    txt("t_claims", "### Claims experience — active renewal", 12, 1, 0, 19),
    bar("w_claims", "ds_claims", "month_date", "total_incurred", "Monthly incurred claims ($)", wtype="line",
        w=12, h=6, x0=0, y0=20, yfmt=USD, scale="temporal"),
]

THEME = {
    "canvasBackgroundColor": {"light": "#FCFCFC", "dark": "#1F272D"},
    "widgetBackgroundColor": {"light": "#FFFFFF", "dark": "#11171C"},
    "fontColor": {"light": "#11171C", "dark": "#E8ECF0"},
    "selectionColor": {"light": "#2272B4", "dark": "#8ACAFF"},
    "visualizationColors": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442"],
    "widgetHeaderAlignment": "LEFT", "widgetCornerRadius": 10,
}

dash = {"datasets": DATASETS,
        "pages": [{"name": "main", "displayName": "HB Renewal Book",
                   "pageType": "PAGE_TYPE_CANVAS", "layoutVersion": "GRID_V1", "layout": layout}],
        "uiSettings": {"theme": THEME,
                       "genieSpace": {"isEnabled": True, "overrideId": GENIE_SPACE, "enablementMode": "ENABLED"}}}

out = pathlib.Path(__file__).with_name("hb_renewal_board.lvdash.json"); out.write_text(json.dumps(dash, indent=1))
w = WorkspaceClient(profile=prof)
ser = json.dumps(dash)
if existing:
    d = w.lakeview.update(existing, Dashboard(display_name="HB Renewal Book — Bricksurance", serialized_dashboard=ser, warehouse_id=wh))
else:
    d = w.lakeview.create(Dashboard(display_name="HB Renewal Book — Bricksurance", serialized_dashboard=ser, warehouse_id=wh,
                                    parent_path=f"/Workspace/Users/{w.current_user.me().user_name}"))
w.lakeview.publish(d.dashboard_id, embed_credentials=True, warehouse_id=wh)
pathlib.Path(__file__).with_name("dashboard_id.txt").write_text(d.dashboard_id)
print("DASHBOARD_ID:", d.dashboard_id)
