import logging

from . import utils

logger = logging.getLogger(__name__)

# Unfortunately, this is not importable in qt designer.
# Qt mandates that this is imported before a QCoreApplication is created,
# but qt designer is itself a Qt application!
# Skip if this fails, will not impact use of qt designer.
try:
    # qtpy has some holes in its web engine support. Fall back to Qt5:
    from PyQt5.QtWebEngineCore import (QWebEngineHttpRequest,
                                       QWebEngineUrlRequestInterceptor)
    from PyQt5.QtWebEngineWidgets import (QWebEnginePage, QWebEngineProfile,
                                          QWebEngineView)
except ImportError as ex:
    QWebEngineHttpRequest = None
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineUrlRequestInterceptor = None
    QWebEngineView = None
    TyphosWebEngineView = None
    TyphosWebRequestInterceptor = None
    logger.warning("Unable to import %s; typhos web views disabled.", ex)
else:
    class TyphosWebRequestInterceptor(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, request_info):
            # request is QWebEngineUrlRequestInfo
            logger.debug("Help navigating to %s", request_info.requestUrl())
            for header, value in utils.HELP_HEADERS.items():
                request_info.setHttpHeader(
                    header.encode("utf-8"),
                    value.encode("utf-8"),
                )

    class TyphosWebEngineView(QWebEngineView):
        def __init__(self, parent=None):
            super().__init__(parent=parent)

            self._interceptor = TyphosWebRequestInterceptor(self)
            self._profile = QWebEngineProfile(self)
            self._profile.setRequestInterceptor(self._interceptor)
            self._page = QWebEnginePage(self._profile, self)
            self.setPage(self._page)
