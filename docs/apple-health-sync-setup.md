# Apple Health Sync Setup

Two options — use whichever works better for you.

---

## Option A: Health Auto Export (Recommended)

**Install the app:** Health Auto Export ($5 one-time) from the App Store.

**Configure the REST API automation:**

1. Open Health Auto Export → **Automations** → **Add Automation** → **REST API**
2. Set the URL: `http://<your-mac-ip>:8000/integrations/health-auto-export`
3. Add header: `X-API-Key: chitiyu-2026`
4. Set method: **POST**
5. Under **Metrics**, enable:
   - Step Count
   - Resting Heart Rate
   - Sleep Analysis
6. Set **Data Range**: Last 2 days (catches yesterday's sleep correctly)
7. Save the automation

**Schedule it via Shortcuts (so it runs daily):**

1. Open Shortcuts → **Automation** tab → **+** → **Time of Day**
2. Set time: **8:00 AM**, Daily
3. Add action: **Run Health Auto Export** (search for it — installed by the app)
4. Choose your automation
5. Turn off **Ask Before Running**

This fires at 8am, unlocks or not, and POST's last 2 days of data to the backend.

**What the payload looks like:**
```json
{
  "data": {
    "metrics": [
      {"name": "step_count", "units": "count", "data": [{"date": "2026-08-08 00:00:00 +0000", "qty": 9123}]},
      {"name": "resting_heart_rate", "units": "bpm", "data": [{"date": "2026-08-08 00:00:00 +0000", "qty": 57}]},
      {"name": "sleep_analysis", "units": "hr", "data": [
        {"date": "2026-08-08 00:00:00 +0000", "qty": 1.2, "value": "asleep_deep"},
        {"date": "2026-08-08 00:00:00 +0000", "qty": 4.8, "value": "asleep_core"}
      ]}
    ]
  }
}
```

The backend parses step_count → steps, resting_heart_rate → resting_hr (averaged across readings),
sleep_analysis → sleep_total_mins (all stages summed) and sleep_deep_mins (asleep_deep only).

---

## Option B: iOS Shortcuts (No App Purchase)

The "Find Health Samples" action hangs because it returns thousands of raw micro-interval samples.
The fix: **aggregate by day** and use a narrow time window.

**Build this Shortcut:**

1. **Get Current Date** → save as variable `today`
2. **Adjust Date** (today, subtract 1 day) → save as variable `yesterday`

**Steps (run for today):**
3. **Find Health Samples** where:
   - Type: **Step Count**
   - Start date: yesterday
   - End date: today
   - **Group By: Day** ← critical, without this it hangs
   - Aggregate: **Sum**
4. **Get Item from List** → First item → save as `steps_value`

**Resting HR:**
5. **Find Health Samples** where:
   - Type: **Resting Heart Rate**
   - Start date: yesterday, End date: today
   - **Group By: Day**, Aggregate: **Average**
6. Save result as `hr_value`

**Sleep (run for yesterday — sleep is attributed to the day it ended):**
7. **Adjust Date** (yesterday, subtract 1 day) → `two_days_ago`
8. **Find Health Samples** where:
   - Type: **Sleep Analysis**
   - Start date: two_days_ago, End date: yesterday
   - **Group By: Day**, Aggregate: **Sum**
9. Save as `sleep_value`

**POST to backend:**
10. **Get Contents of URL**
    - URL: `http://<your-mac-ip>:8000/siri/sync-health`
    - Method: POST
    - Headers: `X-API-Key: chitiyu-2026`, `Content-Type: application/json`
    - Body (JSON):
      ```
      {
        "date": "[yesterday formatted as YYYY-MM-DD]",
        "steps": [steps_value],
        "resting_hr": [hr_value],
        "sleep_total_mins": [sleep_value converted from hours to minutes]
      }
      ```

**Schedule it:** Automation → Time of Day → 8:00 AM daily → Run Shortcut → turn off Ask Before Running.

**Note:** Unlike Health Auto Export, you must have the phone **unlocked** at 8am for this to fire.
If it misses, you can run it manually.

---

## Backend Endpoints

| Endpoint | Use |
|---|---|
| `POST /integrations/health-auto-export` | Health Auto Export app push |
| `POST /siri/sync-health` | Manual Shortcuts push |
| `POST /health/sync` | App or direct API call |
| `GET /health/metrics/today` | Read today's metrics |
| `GET /health/metrics/{date}` | Read any date's metrics |

All endpoints accept partial payloads — sending only steps won't wipe sleep data already stored.

---

## Finding Your Mac's IP

```bash
ipconfig getifaddr en0
```

Use that IP in place of `<your-mac-ip>` above. Make sure your iPhone and Mac are on the same WiFi network.
