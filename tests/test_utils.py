from typhon.utils import load_stylesheet


def test_stylesheet():
    sty = load_stylesheet()
    assert 'QWidget' in sty
