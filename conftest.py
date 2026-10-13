"""
Dam bao goc repo nam trong duong dan import khi chay test.

`pytest.ini` da khai `pythonpath = .`, nhung muc do can pytest >= 7.
File nay la lop du phong, de test chay duoc tren moi phien ban pytest va moi
cach goi (`pytest`, `python -m pytest`, chay tu IDE).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
