#!/usr/bin/env bash
# (Re)deploy public + marts tables into the WrenAI model, then wait for sync.
set -euo pipefail
UI="http://127.0.0.1:8602/api/graphql"
python3 - <<'PY'
import json,urllib.request,time
UI="http://127.0.0.1:8602/api/graphql"
def gql(q,v=None):
    body=json.dumps({"query":q,"variables":v or {}}).encode()
    return json.loads(urllib.request.urlopen(urllib.request.Request(UI,data=body,headers={"Content-Type":"application/json"})).read())
tabs=[t["name"] for t in gql("query{listDataSourceTables{name}}")["data"]["listDataSourceTables"] if t["name"].startswith(("public.","marts."))]
gql("mutation($data:SaveTablesInput!){saveTables(data:$data)}",{"data":{"tables":tabs}})
for _ in range(30):
    if "SYNCRONIZED" in json.dumps(gql("query{modelSync{status}}")): print("SYNCRONIZED",len(tabs),"tables"); break
    time.sleep(4)
PY
