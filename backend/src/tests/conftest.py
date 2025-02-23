import os
import sys
from pathlib import Path

# Get the absolute path to the src directory
src_path = str(Path(__file__).parent.parent.absolute())

# Add the src directory to Python path
sys.path.insert(0, src_path) 