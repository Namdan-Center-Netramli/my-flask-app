# Biodata Attendance System (Flask)

**Login:** `admin` / `admin123`

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

## Notes / Fixes
- Templates have correct `name` attributes (`name`, `district`, `contact`).
- Form methods are `POST` where needed.
- Added basic error messages to show DB insert issues.
- `init_db()` runs at startup to ensure tables & defaults exist.
- SQLite `PRAGMA foreign_keys = ON` and `check_same_thread=False` to avoid thread errors in debug.
