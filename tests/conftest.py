import sys
import os

# Add project root to path FIRST (before any other paths that might have run.py)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Remove any conflicting paths that might contain other run.py files
paths_to_remove = [p for p in sys.path if 'BasicApp' in p or 'MLE' in p]
for path in paths_to_remove:
    sys.path.remove(path)

# Ensure our project root is at position 0 (highest priority)
if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)
