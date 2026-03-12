import requests

# Get first pending job
resp = requests.get("http://localhost:5000/api/jobs")
jobs = resp.json()
job_id = None
for j in jobs:
    if j['id']:
        job_id = j['id']
        break

if job_id:
    details_resp = requests.get(f"http://localhost:5000/api/job/{job_id}/details")
    print("Scheduled Time:", details_resp.json().get('scheduled_time'))
else:
    print("No jobs found")
