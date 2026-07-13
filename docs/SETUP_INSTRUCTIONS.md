# GRN Atlas UI - Automated Setup Guide

This guide explains how to use the automated setup scripts to integrate GRN Atlas UI into your existing React project.

## Overview

Two setup scripts are provided:
- **`setup.sh`** - For macOS and Linux
- **`setup.bat`** - For Windows

Both scripts perform the same operations:
1. ✅ Verify prerequisites (Node.js, npm, git)
2. ✅ Create directory structure
3. ✅ Copy all component files
4. ✅ Copy CSS stylesheets
5. ✅ Copy service files
6. ✅ Copy documentation
7. ✅ Install dependencies
8. ✅ Set up environment variables
9. ✅ Create backups
10. ✅ Display setup summary

## Prerequisites

### System Requirements
- **Node.js** 14+ (Required)
- **npm** 6+ (Required)
- **git** (Recommended, but optional)
- **bash** shell (for Linux/macOS setup.sh)
- **Command Prompt or PowerShell** (for Windows setup.bat)

### Project Requirements
Your existing project must have:
- `package.json` in the root directory
- `src/` directory with existing React files
- Standard React project structure

## Quick Start

### macOS / Linux

```bash
# 1. Download setup script to your project directory
cd ~/path/to/your/grn-atlas-project
curl -O https://raw.githubusercontent.com/kjanik70/grn-atlas/main/setup.sh

# 2. Make it executable
chmod +x setup.sh

# 3. Run the setup script
./setup.sh

# Or run with explicit project path:
./setup.sh ~/path/to/project
```

### Windows

```batch
# 1. Download setup.bat to your project directory
# (Or copy from the distribution package)

# 2. Open Command Prompt or PowerShell in your project directory
cd C:\Users\YourName\Documents\grn-atlas

# 3. Run the setup script
setup.bat

# Or run with explicit project path:
setup.bat C:\path\to\your\project
```

## Detailed Usage

### Step-by-Step (All Platforms)

#### 1. Download the Setup Files

**Option A: Clone repository**
```bash
git clone https://github.com/kjanik70/grn-atlas.git
cd grn-atlas
```

**Option B: Download source file**
- Download `setup.sh` (macOS/Linux) or `setup.bat` (Windows)
- Place in your project directory or temporary location

#### 2. Verify Permissions (Linux/macOS only)

```bash
chmod +x setup.sh  # Make script executable
ls -la setup.sh    # Verify (should show rwxr-xr-x)
```

#### 3. Navigate to Project Directory

**macOS/Linux:**
```bash
cd ~/projects/my-grn-atlas-project
```

**Windows:**
```bash
cd C:\Users\YourName\Documents\grn-atlas
```

#### 4. Run the Setup Script

**macOS/Linux (in project directory):**
```bash
# Option 1: Script in current directory
bash setup.sh

# Option 2: Script elsewhere, specify project path
bash /path/to/setup.sh ~/projects/my-project

# Option 3: Using absolute path
./setup.sh /full/path/to/project
```

**Windows (in project directory):**
```batch
# Option 1: Script in current directory
setup.bat

# Option 2: Script elsewhere, specify project path
setup.bat C:\full\path\to\project

# Option 3: Using PowerShell
powershell -ExecutionPolicy Bypass -File setup.bat
```

#### 5. Monitor Progress

The script will display:
- ✅ Green checkmarks for successful operations
- ⚠️ Yellow warnings for optional steps
- ℹ️ Blue info messages
- ✗ Red errors if something fails

#### 6. Review Output

At the end, you'll see:
- Complete file manifest
- Installation summary
- Next steps
- Pro tips

## What Gets Created

### Directory Structure

After running the setup script, your project will have:

```
your-project/
├── src/
│   ├── components/                          [NEW]
│   │   ├── Sidebar.jsx
│   │   ├── Toolbar.jsx
│   │   ├── ViewTabs.jsx
│   │   ├── NetworkVisualization.jsx
│   │   ├── GeneDetailPanel.jsx
│   │   ├── ComparisonView.jsx
│   │   ├── InterventionDesigner.jsx
│   │   └── PathwayView.jsx
│   ├── services/                            [NEW]
│   │   └── apiService.js
│   ├── styles/                              [NEW]
│   │   ├── theme.css
│   │   ├── GeneNetworkExplorer.css
│   │   ├── Sidebar.css
│   │   ├── Toolbar.css
│   │   ├── ViewTabs.css
│   │   ├── NetworkVisualization.css
│   │   ├── GeneDetailPanel.css
│   │   ├── ComparisonView.css
│   │   ├── InterventionDesigner.css
│   │   └── PathwayView.css
│   ├── App.jsx                              [EXISTING - YOU UPDATE THIS]
│   └── ... other files
├── docs/                                    [NEW]
│   ├── README.md
│   ├── INTEGRATION_GUIDE.md
│   ├── PROJECT_SUMMARY.md
│   ├── QUICK_REFERENCE.md
│   └── backend_example.py
├── .env.local                               [NEW]
├── package.json                             [UPDATED]
├── package.json.backup                      [NEW]
└── ... other files
```

## After Setup

### 1. Update App.jsx

The setup script **does NOT modify your existing App.jsx** to prevent data loss.

You need to manually update it:

**Before:**
```jsx
// Your existing App.jsx
export default function App() {
  return (
    <div>
      {/* Your existing app content */}
    </div>
  );
}
```

**After:**
```jsx
import GeneNetworkExplorer from './components/GeneNetworkExplorer';
import './styles/theme.css';

export default function App() {
  return <GeneNetworkExplorer />;
}
```

### 2. Configure Environment

Edit `.env.local` (created by setup script):

```bash
# .env.local
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_API_TIMEOUT=30000
REACT_APP_DEFAULT_CONFIDENCE=0.6
REACT_APP_MAX_NETWORK_NODES=1000
REACT_APP_DEFAULT_LAYOUT=cose
```

### 3. Install Additional Dependencies (if needed)

The setup script installs:
- ✅ cytoscape@^3.28.1
- ✅ cytoscape-popper@^2.0.0
- ✅ popper.js@^1.16.1

If you need other packages, install manually:
```bash
npm install <package-name>
```

### 4. Start Development

```bash
npm start
# Opens http://localhost:3000
```

### 5. Set Up Backend

Follow the guide in `docs/INTEGRATION_GUIDE.md`:
```bash
python -m uvicorn backend_example:app --reload
# Starts on http://localhost:8000
```

### 6. Commit to Git

```bash
cd your-project-directory
git add .
git commit -m "feat: Add GRN Atlas UI - complete implementation (all 5 phases)"
git push origin main
```

## Troubleshooting

### Script Won't Execute (Linux/macOS)

**Error:** `bash: ./setup.sh: Permission denied`

**Solution:**
```bash
chmod +x setup.sh
./setup.sh
```

### Script Not Found (All Platforms)

**Error:** `bash: setup.sh: No such file or directory`

**Solution:**
1. Verify script is in the directory: `ls setup.sh`
2. Use absolute path: `bash /full/path/to/setup.sh`
3. Download again from source

### Node/npm Not Found

**Error:** `npm: command not found`

**Solution:**
1. Install Node.js from https://nodejs.org/
2. Restart terminal/Command Prompt
3. Verify: `node --version` and `npm --version`

### Project Path Error

**Error:** `Project path does not exist`

**Solution:**
1. Verify path exists: `ls /your/path` (Linux/macOS) or `dir C:\your\path` (Windows)
2. Use absolute path instead of relative
3. Ensure no typos in path

### Git Not Found (Warning)

**Warning:** `git is not installed (optional, but recommended)`

**Solution:** Optional, but install git from https://git-scm.com/ for version control

### Package Installation Fails

**Error:** `npm install failed`

**Possible Causes:**
- Internet connection issue
- npm registry down
- Disk space issue

**Solutions:**
1. Check internet connection
2. Try again: `npm install`
3. Clear cache: `npm cache clean --force`
4. Check disk space

### Files Already Exist

**Warning:** `File already exists: xyz.jsx (skipping)`

**This is normal!** The script won't overwrite existing files. 

If you want to force update:
1. Delete the file first
2. Run setup script again

## Advanced Options

### Using with Docker

If your project uses Docker:

```bash
# Inside Docker container
docker exec -it my-project bash
cd /app
./setup.sh
```

### Running from Different Directory

```bash
# Setup files in one location, project elsewhere
bash /setup/location/setup.sh /project/location/path
```

### Headless / Non-Interactive

The setup scripts are designed to run non-interactively. Combine with automation:

```bash
# Run in CI/CD pipeline
bash setup.sh > setup.log 2>&1
git add .
git commit -m "Auto: Setup GRN Atlas UI"
```

### Manual Setup Alternative

If the scripts don't work, you can do it manually:

```bash
# 1. Create directories
mkdir -p src/components src/services src/styles docs

# 2. Copy files (copy-paste into terminal)
cp -r components/* src/components/
cp services/* src/services/
cp styles/* src/styles/
cp *.md docs/
cp backend_example.py docs/

# 3. Copy environment template
cp .env.example .env.local

# 4. Install dependencies
npm install cytoscape@^3.28.1 cytoscape-popper@^2.0.0 popper.js@^1.16.1

# 5. Verify files exist
ls -la src/components/
ls -la src/services/
ls -la src/styles/
```

## Verification Checklist

After running the setup script, verify:

- [ ] `src/components/` contains 9 .jsx files
- [ ] `src/services/` contains 1 apiService.js
- [ ] `src/styles/` contains 10 .css files
- [ ] `docs/` contains 5 documentation files
- [ ] `.env.local` exists (or `.env`)
- [ ] `node_modules/cytoscape/` exists
- [ ] `node_modules/cytoscape-popper/` exists
- [ ] `package.json` updated with new dependencies
- [ ] `package.json.backup` created

Quick check:
```bash
# Linux/macOS
find src -type f | wc -l    # Should be ~20
find docs -type f | wc -l   # Should be ~5

# Windows
dir /s src\*.jsx | find /c ".jsx"    # Should show 9
dir /s docs\*.md | find /c ".md"     # Should show 5
```

## Getting Help

### Check Documentation

1. **Quick Reference:** `docs/QUICK_REFERENCE.md`
2. **Full Guide:** `docs/README.md`
3. **Backend Setup:** `docs/INTEGRATION_GUIDE.md`
4. **Issues:** Check `docs/README.md` Troubleshooting section

### Review Script Output

The script displays detailed progress and next steps. Re-read the output carefully.

### Manual Verification

```bash
# Check file count
ls -la src/components/      # Should see 9 files
ls -la src/services/        # Should see apiService.js
ls -la src/styles/          # Should see 10 files

# Check dependencies
npm list cytoscape
npm list cytoscape-popper

# Check environment
cat .env.local              # Should show API URL
```

## Success Indicators

The setup was successful if:

✅ No error messages (warnings are OK)  
✅ All files copied without skipping  
✅ Dependencies installed  
✅ Documentation present in `docs/`  
✅ `.env.local` created  
✅ Output shows file manifest  

Next: Update `App.jsx` and run `npm start`!

## Related Files

- **setup.sh** - Linux/macOS setup script
- **setup.bat** - Windows setup script
- **docs/README.md** - Full documentation
- **docs/INTEGRATION_GUIDE.md** - Backend integration
- **docs/PROJECT_SUMMARY.md** - Quick overview
- **.env.example** - Environment template

## Questions?

1. Read `docs/README.md` for comprehensive documentation
2. Check `docs/INTEGRATION_GUIDE.md` for backend setup
3. Review script output carefully
4. Verify all prerequisites are installed

Good luck! 🚀
