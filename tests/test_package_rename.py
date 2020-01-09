
def test_import_smoke():
    import typhon
    import typhos


def test_class_compat():
    from typhon.suite import TyphonSuite
    from typhos.suite import TyphosSuite

    assert TyphonSuite is TyphosSuite