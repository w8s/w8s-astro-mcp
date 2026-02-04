"""Interactive installation helper for Swiss Ephemeris (swetest)."""

import subprocess
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class InstallationHelper:
    """Guides user through swetest installation."""
    
    def __init__(self):
        self.swetest_path: Optional[str] = None
    
    def check_swetest(self, path: str = "swetest") -> Dict[str, Any]:
        """
        Check if swetest is available and working.
        
        Args:
            path: Path to swetest binary
            
        Returns:
            Dict with status, version, path info
        """
        result = {
            "installed": False,
            "in_path": False,
            "version": None,
            "path": None,
            "message": ""
        }
        
        # Try the provided path
        try:
            proc = subprocess.run(
                [path, "-h"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if proc.returncode == 0:
                # Extract version from help text
                for line in proc.stdout.split('\n'):
                    if 'Version:' in line:
                        result["version"] = line.split('Version:')[1].strip()
                        break
                
                result["installed"] = True
                result["path"] = path
                
                # Check if it's in PATH
                if path == "swetest":
                    result["in_path"] = True
                    result["message"] = f"✅ swetest found in PATH (version {result['version']})"
                else:
                    result["in_path"] = False
                    result["message"] = f"✅ swetest found at {path} (version {result['version']}), but not in PATH"
                
                return result
                
        except FileNotFoundError:
            result["message"] = "❌ swetest not found"
        except subprocess.TimeoutExpired:
            result["message"] = "⚠️  swetest found but timed out"
        except Exception as e:
            result["message"] = f"❌ Error checking swetest: {e}"
        
        return result
    
    def find_swetest_in_common_locations(self) -> Optional[str]:
        """
        Search for swetest in common installation locations.
        
        Returns:
            Path to swetest if found, None otherwise
        """
        common_paths = [
            "/usr/local/bin/swetest",
            "/usr/bin/swetest",
            "/opt/homebrew/bin/swetest",
            str(Path.home() / "bin" / "swetest"),
            str(Path.home() / ".local" / "bin" / "swetest"),
            # Common clone locations
            str(Path.home() / "swisseph" / "swetest"),
            str(Path.home() / "software" / "swisseph" / "swetest"),
            str(Path.home() / "git" / "swisseph" / "swetest"),
        ]
        
        # Also search common parent directories for swisseph subdirectory
        search_dirs = [
            Path.home() / "Documents",
            Path.home() / "dev",
            Path.home() / "projects",
        ]
        
        for search_dir in search_dirs:
            if search_dir.exists():
                # Look for swisseph in subdirectories
                for subdir in search_dir.iterdir():
                    if subdir.is_dir():
                        swetest_path = subdir / "swisseph" / "swetest"
                        if swetest_path.exists():
                            common_paths.append(str(swetest_path))
        
        for path in common_paths:
            if Path(path).exists():
                status = self.check_swetest(path)
                if status["installed"]:
                    return path
        
        return None
    
    def get_installation_guide(self) -> str:
        """
        Get step-by-step installation instructions.
        
        Returns:
            Markdown-formatted installation guide
        """
        return """
# Swiss Ephemeris (swetest) Installation Guide

## Option 1: Clone and Build from Source (Recommended)

### Step 1: Clone the Repository
```bash
# Clone to a directory of your choice (examples below)
git clone https://github.com/aloistr/swisseph.git
cd swisseph

# Or clone to a specific location:
# mkdir -p ~/software && cd ~/software
# git clone https://github.com/aloistr/swisseph.git
# cd swisseph
```

### Step 2: Build swetest
```bash
# Build all executables (swetest, swemini, swevents)
make
```

This creates three executables:
- `swetest` - Main ephemeris calculator (what we need)
- `swemini` - Minimal version
- `swevents` - Event calculator

### Step 3: Add to PATH

Choose one method:

**Method A: Symlink to system bin (requires sudo)**
```bash
# From inside the swisseph directory:
sudo ln -s $(pwd)/swetest /usr/local/bin/swetest
```

**Method B: Add to your shell PATH (no sudo needed)**

For bash (~/.bashrc):
```bash
# From inside the swisseph directory:
echo "export PATH=\"\$(pwd):\$PATH\"" >> ~/.bashrc
source ~/.bashrc
```

For zsh (~/.zshrc):
```bash
# From inside the swisseph directory:
echo "export PATH=\"\$(pwd):\$PATH\"" >> ~/.zshrc
source ~/.zshrc
```

For fish (~/.config/fish/config.fish):
```bash
# From inside the swisseph directory:
set SWISSEPH_DIR (pwd)
echo "set -gx PATH $SWISSEPH_DIR \$PATH" >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

### Step 4: Verify Installation
```bash
swetest -h
# Should show version 2.10.03
```

## Option 2: Use Full Path (No PATH modification)

If you don't want to modify PATH, you can configure w8s-astro-mcp to use the full path:

```python
# When running the MCP server, specify the full path:
# e.g., /home/username/software/swisseph/swetest
```

## Option 3: Download Pre-built Binary (macOS/Linux)

Visit https://github.com/aloistr/swisseph/tree/master/[platform]/programs
and download the appropriate binary for your platform.

## Troubleshooting


**Error: "swetest not found"**
- Check if build succeeded: `ls ./swetest` (from swisseph directory)
- Verify PATH: `echo $PATH | grep swisseph`
- Try full path: `/path/to/swisseph/swetest -h`

**Error: "Permission denied"**
- Make executable: `chmod +x ./swetest` (from swisseph directory)

**Build errors:**
- Install build tools: `xcode-select --install` (macOS)
- Or install gcc: `sudo apt-get install build-essential` (Linux)

## License Notice

Swiss Ephemeris is dual-licensed:
- **AGPL (free)**: For open source projects
- **Professional License (paid)**: For proprietary software

See LICENSE_NOTICE.md for details.
"""
    
    def get_quick_fix_guide(self, found_path: Optional[str] = None) -> str:
        """
        Get quick fix instructions based on current situation.
        
        Args:
            found_path: Path where swetest was found (if any)
            
        Returns:
            Targeted fix instructions
        """
        if found_path:
            return f"""
## Quick Fix: swetest found but not in PATH

swetest is installed at: `{found_path}`

**Option A: Add to PATH (recommended)**
```bash
echo 'export PATH="{Path(found_path).parent}:$PATH"' >> ~/.zshrc
source ~/.zshrc
```


**Option B: Symlink (requires sudo)**
```bash
sudo ln -s {found_path} /usr/local/bin/swetest
```

**Option C: Use full path**
Configure w8s-astro-mcp to use: `{found_path}`
"""
        else:
            return self.get_installation_guide()
    
    def diagnose(self) -> Dict[str, Any]:
        """
        Run full diagnostic and return status report.
        
        Returns:
            Dict with diagnosis and recommendations
        """
        diagnosis = {
            "status": "unknown",
            "swetest_in_path": False,
            "swetest_found": False,
            "found_at": None,
            "recommendations": []
        }
        
        # Check if in PATH
        path_status = self.check_swetest("swetest")
        diagnosis["swetest_in_path"] = path_status["installed"]
        
        if path_status["installed"]:
            diagnosis["status"] = "ready"
            diagnosis["swetest_found"] = True
            diagnosis["found_at"] = "PATH"
            diagnosis["recommendations"].append("✅ All set! swetest is ready to use.")
            return diagnosis
        
        # Search common locations
        found_path = self.find_swetest_in_common_locations()
        
        if found_path:
            diagnosis["status"] = "needs_path"
            diagnosis["swetest_found"] = True
            diagnosis["found_at"] = found_path
            diagnosis["recommendations"].append(
                f"⚠️  swetest found at {found_path} but not in PATH."
            )
            diagnosis["recommendations"].append(
                "Run the setup_swetest tool to add it to your PATH."
            )
            return diagnosis
        
        # Not found anywhere
        diagnosis["status"] = "not_installed"
        diagnosis["recommendations"].append(
            "❌ swetest not found. Installation required."
        )
        diagnosis["recommendations"].append(
            "Run the setup_swetest tool for installation instructions."
        )
        
        return diagnosis
