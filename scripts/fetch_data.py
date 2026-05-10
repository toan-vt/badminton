import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from badminton_availability.fetch import main


if __name__ == "__main__":
    main()

