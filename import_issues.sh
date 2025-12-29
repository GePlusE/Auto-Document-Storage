#!/bin/bash
repo="GePlusE/Auto-Document-Storage"

# Sicherstellen, dass die Basis-Labels existieren
gh label create done --color "0E8A16" --repo $repo 2>/dev/null
gh label create enhancement --color "A2EEEF" --repo $repo 2>/dev/null

data=(
"F01: Manual Dry-Run start|Core|Done"
"F02: Show list of all PDFs in Input Directory|Core|Done"
"F03: Show suggestions: new filename + target folder|Core|Done"
"F04: Manually confirm/reject suggestions per PDF|Core|Done"
"F05: Manually edit and confirm suggestions|Core|Done"
"F06: PDF Preview (Split View)|Core|Done"
"F07: Multi-select in list|UI / UX|Done"
"F08: Batch Actions (Accept/Reject/Move)|UI / UX|Done"
"F09: Status per PDF (Pending/Accepted/etc.)|UI / UX|Done"
"F10: Sort by Date/Name/Sender/Confidence|UI / UX|Done"
"F11: Filter: Unclear/Errors/Low Confidence|UI / UX|Done"
"F12: Search (Filename, Sender, Folder)|UI / UX|Done"
"F13: Session-Undo|UI / UX|Done"
"F14: Action-History|UI / UX|Done"
"F15: Display Confidence (Stage1/Stage2)|Analytics|Done"
"F16: “Why?”-Panel (Short reasoning)|Analytics|Done"
"F17: Show matching Mapping Rule|Rules|Planned"
"F18: Highlight matching text patterns|Rules|Planned"
"F19: Toggle: Mapping/Heuristic vs. LLM active|Core|Planned"
"F20: Preview Controls (Zoom, Page Navigation)|UI / UX|Done"
"F21: Thumbnails/Page List in Preview|UI / UX|Done"
"F22: Search within PDF (Textlayer/OCR)|UI / UX|Planned"
"F23: Sensitive mode (Blurred Preview)|Security|Done"
"F24: “Open in Finder” / “Reveal file” Buttons|UI / UX|Planned"
"F25: Live-Validation for filenames|UI / UX|Done"
"F26: Collision Preview (_1, _2)|Core|Done"
"F27: Check folder existence + Create Option|Core|Done"
"F28: Quick actions (Reset/Fallback)|UI / UX|Done"
"F29: Naming Templates ({{date}}_{{sender}})|Rules|Done"
"F30: Folder Picker (GUI)|UI / UX|Done"
"F31: Open/Switch Mapping File in GUI|Rules|Done"
"F32: Rule Builder GUI|Rules|Planned"
"F33: Rule Testing (Live Match Preview)|Rules|Planned"
"F34: “Learn from decisions” (Save as Rule)|Rules|Planned"
"F35: Export/Import Mapping JSON|Rules|Planned"
"F36: Rule Priorities Management|Rules|Planned"
"F37: launchd Status Display|Automation|Planned"
"F38: Load/Unload Agent Buttons|Automation|Planned"
"F39: Scheduler UI (plist Editor)|Automation|Planned"
"F40: macOS Notifications after Run|Automation|Planned"
"F41: Safe Mode (Copy only, no move)|Core|Planned"
"F42: Background watcher (Live Update)|Automation|Planned"
"F43: DB Viewer for LLM Outputs|Analytics|Done"
"F44: Low-confidence Inbox|Analytics|Planned"
"F45: Error Inbox + Retry Logic|Analytics|Planned"
"F46: Metrics (Quota, Top Sender, Avg Confidence)|Analytics|Planned"
"F47: Export: CSV/JSON Report|Analytics|Planned"
"F48: Global “No LLM mode”|Security|Planned"
"F49: Data Minimization (Min. Sender Cues)|Security|Planned"
"F50: “Open data folder” + Warning|Security|Planned"
"F51: “Purge” Functions: Logs & DB|Security|Planned"
"F52: Keyboard Shortcuts (A/R/E/Space)|UI / UX|Planned"
"F53: Drag & Drop PDFs into Window|UI / UX|Planned"
"F54: Persisted UI layout|UI / UX|Planned"
"F55: Multi-window Support (Rules Editor)|UI / UX|Done"
"F56: “Dry-run diff” View|Core|Done"
"Create Setup-Guide|Guide|Planned"
"Create Onboarding-Guide|Guide|Planned"
"Remove unnecessary UI elements|Clean|Planned"
"Remove 'reveal' button|Clean|Planned"
"Add refresh feature for PDF Table|Core|Planned"
"Add loading indicator for LLM|UI / UX|Planned"
"Add MacOS notifications|UI / UX|Planned"
"Feature: run selected PDFs only|Core|Planned"
"Create full downloadable program|Feature|Planned"
"Add update function to menu bar|Security|Planned"
"Add automatic update toggle|Security|Planned"
"Pre-select LLM specs for M-Chips|Core|Planned"
"Bugfix: Stage 2 LLM usage frequency|Bugfix|Planned"
"Add 'About' menu|Core|Planned"
"Add folder hints for LLM|Feature|Planned"
"Adjust LLM prompt|Feature|Planned"
"Clean Repository|Clean|Planned"
"Create Software Logo|Core|Planned"
"Re-think software name|Core|Planned"
)

for row in "${data[@]}"; do
    IFS="|" read -r title cat status <<< "$row"
    
    # Check if issue already exists to avoid duplicates
    exists=$(gh issue list --repo $repo --search "$title" --json number --jq '.[0].number')
    if [ ! -z "$exists" ]; then
        echo "Skipping (already exists): $title"
        continue
    fi

    echo "Creating: $title..."
    if [ "$status" == "Done" ]; then
        gh issue create --repo $repo --title "$title" --body "Category: $cat" --label "enhancement" --label "done"
    else
        gh issue create --repo $repo --title "$title" --body "Category: $cat" --label "enhancement"
    fi
    sleep 1
done
