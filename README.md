# Auto-Document-Storage

Automatically detects new files (e.g., PDFs) in a specified directory, renames them based on a structured naming convention, and moves them into a target folder. The target folder is automatically created based on the filename prefix if it does not exist.

---

## 📁 How It Works

1. The script looks into a directory (`directory_to_clean`) for new files.
2. Files with a double-underscore `__` in their names are renamed and moved based on their prefix.
3. The files are sorted into subfolders based on the provided prefix (which becomes the folder name).

---

## 🧠 Filename Logic

- A valid file must include **at least one double-underscore (`__`)**.

### ➕ Examples

- `Invoices__Report.pdf`  
  → Moved to folder: `Invoices/`  
  → Renamed: `YYYY-MM-DD Report.pdf`

- `Clients__Invoice__Jan23.pdf`  
  → Moved to folder: `Clients/`  
  → Renamed: `YYYY-MM-DD Invoice.pdf`

- `FileWithoutUnderscore.pdf`  
  → Will be **ignored** (not moved or renamed)

- Multiple files with the same target name get a suffix like `_1`, `_2`, etc.

---

## 🛠 Setup: Configuration (`credentials.py`)

Create a file named `credentials.py` in the same directory as `Script.py` with the following content:

```python
directory_to_clean = "/full/path/to/input/directory"
target_directory = "/full/path/to/target/directory"
types_to_ignore = [".DS_Store", ".dmg", ".zip", ".icloud"]
```

> 🔒 Tip: You can duplicate and rename the `sample_credentials.py` file to get started.

---

## ⚙️ Automation Setup (macOS Only)

To automate the script to run **once, 10 minutes after login**, follow these steps:

### 1. Create a shell script:

File: `run_after_login.sh`

```bash
#!/bin/bash
sleep 600
/usr/local/bin/python3 /Path/to/Project/Auto-Document-Storage/Script.py
```

Make it executable:
```bash
chmod +x run_after_login.sh
```

### 2. Create a Launch Agent:

File: `~/Library/LaunchAgents/com.yourname.autodoc.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.yourname.autodoc</string>

    <key>ProgramArguments</key>
    <array>
      <string>/Path/to/Project/Auto-Document-Storage/run_after_login.sh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>
  </dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.yourname.autodoc.plist
```

---

## 📄 Logging

All operations (renamed, moved, skipped files) are logged to:
```
/Users/yourusername/CodeProjects/Auto-Document-Storage/LogFile.log
```

For setup or system errors, temporary logs (optional) can be found at:
```
/tmp/autodoc_stdout.log
/tmp/autodoc_stderr.log
```

---

## ❌ Deprecated: Cron Setup

Previously, the script could be run with `cron`, but this is no longer recommended on macOS. Use `launchd` for more reliability and system integration.

---

## ✅ Summary

- Automatically organizes and renames documents by filename convention
- Easy to configure
- Seamlessly integrates into your macOS login flow
