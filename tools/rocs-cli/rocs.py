from pathlib import Path
import sys
root = Path(__file__).resolve().parent
sys.path[:0] = [str(root / 'runtime'), str(root / 'src')]
from rocs_cli.__main__ import main
main()
