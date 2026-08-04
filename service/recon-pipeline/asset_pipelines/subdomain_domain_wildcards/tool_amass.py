import subprocess

process = subprocess.Popen(
    [
        "amass",
        "enum",
        "-d",
        "google.com",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

for line in process.stdout:
    print(line.rstrip())