import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest


@pytest.fixture(autouse=True)
def _db_devre_sifirla():
    from yuz_tanima_app import veritabani
    veritabani.hata_durumunu_sifirla()
    yield
    veritabani.hata_durumunu_sifirla()
