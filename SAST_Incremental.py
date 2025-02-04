import requests
import subprocess
import sys
import os

config_template = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<Configuration>
    <Targets>
        <Target path=".">~TARGETS
        </Target>
    </Targets>
</Configuration>
"""

api_key = {
  "KeyId": sys.argv[1],
  "KeySecret": sys.argv[2]
}
app_id = sys.argv[3]

class ASoCIncremental():
    def __init__(self, api_key, app_id, dc=""):
        self.api_key = api_key
        self.app_id = app_id
        if len(dc) > 0:
            dc = f"{dc}."
        self.url_base = f"https://{dc}cloud.appscan.com"
        self.latest_execution_id = ""
        self.last_commit = ""
        self.session = requests.Session()

    def login(self):
        url = f"{self.url_base}/api/v4/Account/ApiKeyLogin"
        r = self.session.post(url, json=self.api_key)
        if r.status_code == 200:
            obj = r.json()
            self.session.headers.update({"Authorization": f"Bearer {obj['Token']}"})
            return True
        return False
        
    def get_last_scan_execution(self):
        url = f"{self.url_base}/api/v4/Scans"
        params = {
            "$top": "1",
            "$filter": f"AppId eq {self.app_id} and Technology eq 'StaticAnalyzer'",
            "$orderby": "CreatedAt desc"
        }
        r = self.session.get(url, params=params)
        if r.status_code == 200:
            obj = r.json()
            self.latest_execution_id = obj["Items"][0]["LatestExecution"]["Id"]
            return True
        return False
    
    def get_last_commit(self):
        url = f"{self.url_base}/api/v4/Scans/SastExecution/{self.latest_execution_id}"
        r = self.session.get(url)
        if r.status_code == 200:
            obj = r.json()
            self.last_commit = obj["GitCommitId"]
            return self.last_commit is not None
        return False
    
    def get_changed_files(self, since_commit):
        out = subprocess.check_output(f"/usr/bin/git diff --name-only HEAD {since_commit}", shell=True)
        out = out.decode().strip().split("\n")
        return out
        
    def write_config(self, path="appscan-config.xml"):
        targets = ""
        files = self.get_changed_files(self.last_commit)
        print("Changed Files:")
        for file in files:
            targets += f"\n\t\t<Include>{file}</Include>"
            print(f"\t{file}")
        config = config_template.replace("~TARGETS", targets)
        print("Writing Config File:")
        print(config)
        with open(path, "w") as f:
            f.write(config)
        return path
    
    def del_config(self, path="appscan-config.xml"):
        if os.path.exists(path):
            os.remove(path)

print("==== ASoC SAST Incremental ====")
ai = ASoCIncremental(api_key, app_id)
print("Fetching last scan execution Id")
if ai.login():
    print("ASoC API Login: Successful")
else:
    print("ASoC API Login: Failed, aborting")
    sys.exit(1)
ai.get_last_scan_execution()

print(f"Last Scan Execution Id: {ai.latest_execution_id}")
if ai.get_last_commit():
    print(f"Last Scanned Commit: {ai.last_commit}")
    ai.write_config()
else:
    print("No last commit found. Scanning everything")
    ai.del_config()
print("==== ASoC SAST Incremental Complete ====") 
