import subprocess
import json

process = subprocess.Popen(
    [
        "subfinder",
        "-d",
        "google.com",
        "-json",
        "-silent",
    ],
    stdout=subprocess.PIPE,
    text=True,
)

for line in process.stdout:
    item = json.loads(line)

    print(item)