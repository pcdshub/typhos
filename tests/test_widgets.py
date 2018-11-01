from typhon.widgets import TyphonSidebarItem
from typhon.suite import SidebarParameter


def test_sidebar_item():
    param = SidebarParameter(name='test', embeddable=True)
    item = TyphonSidebarItem(param, 0)
    assert len(item.toolbar.actions()) == 3
    assert item.open_action.isEnabled()
    assert item.embed_action.isEnabled()
    assert not item.hide_action.isEnabled()
    item.open_requested(True)
    assert not item.open_action.isEnabled()
    assert not item.embed_action.isEnabled()
    assert item.hide_action.isEnabled()
    item.hide_requested(True)
    assert item.open_action.isEnabled()
    assert item.embed_action.isEnabled()
    assert not item.hide_action.isEnabled()
    item.embed_requested(True)
    assert not item.open_action.isEnabled()
    assert not item.embed_action.isEnabled()
    assert item.hide_action.isEnabled()
