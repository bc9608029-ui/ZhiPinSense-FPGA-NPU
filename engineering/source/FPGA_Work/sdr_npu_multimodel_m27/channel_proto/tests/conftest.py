import sys
from pathlib import Path

# Make the channel_proto modules importable regardless of pytest's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
