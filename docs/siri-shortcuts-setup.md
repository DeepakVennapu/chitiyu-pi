# Siri Shortcuts Setup Guide

Base URL: `https://api.chitiyu.deevana.uk`
API Key: your value from `.env` → `API_KEY`

---

## Shortcut 1 — Log Meal

**Trigger:** "Log meal" (or tap shortcut)

**Actions:**
1. **Dictate Text** — Prompt: "What did you eat?"
2. **Get Contents of URL**
   - URL: `https://api.chitiyu.deevana.uk/siri/log-meal`
   - Method: `POST`
   - Headers:
     - `Content-Type`: `application/json`
     - `X-API-Key`: `<your API key>`
   - Request Body: `JSON`
     ```json
     {
       "text": "[Dictated Text]",
       "user_id": 1
     }
     ```
   - (Use the "Dictated Text" magic variable from step 1 for the `text` value)
3. **Get Dictionary Value** — Key: `spoken`, Dictionary: `Contents of URL`
4. **Speak Text** — Text: `Dictionary Value`

---

## Shortcut 2 — Log Expense

**Trigger:** "Log expense" (or tap shortcut)

**Actions:**
1. **Dictate Text** — Prompt: "What did you spend?"
2. **Get Contents of URL**
   - URL: `https://api.chitiyu.deevana.uk/siri/log-expense`
   - Method: `POST`
   - Headers:
     - `Content-Type`: `application/json`
     - `X-API-Key`: `<your API key>`
   - Request Body: `JSON`
     ```json
     {
       "text": "[Dictated Text]",
       "user_id": 1
     }
     ```
3. **Get Dictionary Value** — Key: `spoken`, Dictionary: `Contents of URL`
4. **Speak Text** — Text: `Dictionary Value`

> Note: While the Finance domain is now live, the Siri expense shortcut currently returns an acknowledgment but does not persist the expense to the database. Confirm expense logging in the app after using this shortcut.

---

## Shortcut 3 — Add Task

**Trigger:** "Add task" (or tap shortcut)

**Actions:**
1. **Dictate Text** — Prompt: "What's the task?"
2. **Get Contents of URL**
   - URL: `https://api.chitiyu.deevana.uk/siri/add-task`
   - Method: `POST`
   - Headers:
     - `Content-Type`: `application/json`
     - `X-API-Key`: `<your API key>`
   - Request Body: `JSON`
     ```json
     {
       "text": "[Dictated Text]",
       "user_id": 1
     }
     ```
3. **Get Dictionary Value** — Key: `spoken`, Dictionary: `Contents of URL`
4. **Speak Text** — Text: `Dictionary Value`

---

## Shortcut 4 — How Are My Macros?

**Trigger:** "How are my macros?" (or "Macros" — tap shortcut)

**Actions:**
1. **Get Contents of URL**
   - URL: `https://api.chitiyu.deevana.uk/siri/macros?user_id=1`
   - Method: `GET`
   - Headers:
     - `X-API-Key`: `<your API key>`
2. **Get Dictionary Value** — Key: `spoken`, Dictionary: `Contents of URL`
3. **Speak Text** — Text: `Dictionary Value`

---

## Shortcut 5 — Apple Health Sync

This shortcut runs automatically at 8:00 PM daily via Automation. It reads HealthKit data and pushes it to Chitiyu.

**Actions:**
1. **Find Health Samples** (Steps)
   - Sample Type: `Steps`
   - Time Range: Today
   - Aggregate: Sum
2. **Set Variable** — `steps` = `Health Samples`
3. **Find Health Samples** (Heart Rate — Resting)
   - Sample Type: `Resting Heart Rate`
   - Time Range: Last 24 Hours
   - Aggregate: Average
4. **Set Variable** — `resting_hr` = `Health Samples`
5. **Find Health Samples** (Sleep Analysis — Deep)
   - Sample Type: `Sleep Analysis`
   - Filter by `Stage`: `Deep`
   - Time Range: Last 24 Hours
   - Aggregate: Sum of duration (in minutes)
6. **Set Variable** — `deep_mins` = `Health Samples`
7. **Find Health Samples** (Sleep Analysis — all stages for total)
   - Sample Type: `Sleep Analysis`
   - Filter by `Stage`: `Asleep` (or use all sleep stages and sum)
   - Time Range: Last 24 Hours
   - Aggregate: Sum of duration (in minutes)
8. **Set Variable** — `total_mins` = `Health Samples`
9. **Get Contents of URL**
   - URL: `https://api.chitiyu.deevana.uk/health/sync`
   - Method: `POST`
   - Headers:
     - `Content-Type`: `application/json`
     - `X-API-Key`: `<your API key>`
   - Request Body: `JSON`
     ```json
     {
       "date": "[Current Date — formatted as YYYY-MM-DD]",
       "steps": [steps],
       "sleep_deep_mins": [deep_mins],
       "sleep_total_mins": [total_mins],
       "resting_hr": [resting_hr]
     }
     ```
   - Use the magic variables from steps 2, 4, 6, 8 for the numeric fields.
   - For `date`: add a **Format Date** action before step 9 — format `Current Date` as `ISO 8601` or custom format `yyyy-MM-dd`.

**Automation setup:**
- Open Shortcuts → Automation → New Automation
- Trigger: Time of Day → 8:00 PM → Daily
- Action: Run Shortcut → `Apple Health Sync`
- Uncheck "Ask Before Running" so it fires silently

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Siri says "There was a problem" | Check X-API-Key header is set exactly; verify Cloudflare tunnel is up |
| "Get Contents of URL" returns empty | Confirm the base URL resolves: `curl https://api.chitiyu.deevana.uk/health/metrics/today` |
| Health sync stores 0 steps | HealthKit permissions — go to Health app → Sharing → Apps and confirm Shortcuts has Steps access |
| Shortcut fires but spoken is silent | "Speak Text" action requires TTS enabled; test with "Show Notification" first to see the raw response |
