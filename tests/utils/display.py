from pydm import Display


class TestDisplay(Display):
    is_from_test_file = True

    # HACK to load a UI-less file
    def ui_filepath(self):
        return None
