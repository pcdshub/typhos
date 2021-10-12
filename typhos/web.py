import logging
import urllib.parse

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
    TyphosWebEnginePage = None
    TyphosWebEngineView = None
    TyphosWebRequestInterceptor = None
    logger.warning("Unable to import %s; typhos web views disabled.", ex)
else:
    class TyphosWebRequestInterceptor(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, request_info):
            """
            This hook happens before each navigation.  We use it to
            (optionally) inject the user-configured headers.
            """
            # request is QWebEngineUrlRequestInfo
            url = request_info.requestUrl().toString()
            add_headers = should_add_headers(url)
            logger.debug(
                "Help navigating to %s (add headers=%s)",
                url, add_headers
            )
            if add_headers:
                for header, value in utils.HELP_HEADERS.items():
                    request_info.setHttpHeader(
                        header.encode("utf-8"),
                        value.encode("utf-8"),
                    )

    class TyphosWebEnginePage(QWebEnginePage):
        def javaScriptConsoleMessage(
            self, level, message, line_number, source_id
        ):
            """
            This hook redirects javascript console messages to Python logging.

            The default is normally to log directly to standard output or
            error, so with this hook we can at least optionally filter
            javascript log messages.
            """
            logger.debug(
                "[WebEngine] level=%s %s:%s %s",
                level, source_id, line_number, message
            )

    class TyphosWebEngineView(QWebEngineView):
        def __init__(self, parent=None):
            super().__init__(parent=parent)

            # Configure the intercepter for adding headers
            interceptor = TyphosWebRequestInterceptor(self)
            profile = QWebEngineProfile(self)
            profile.setRequestInterceptor(interceptor)

            # Use our custom page that will allow us to filter out javascript
            # log messages
            page = TyphosWebEnginePage(profile, self)
            self.setPage(page)


def should_add_headers(url):
    """
    Should Typhos add the pre-configured headers when navigating to ``url``?

    Avoids sharing tokens with unrelated sites that the user may click.

    Parameters
    ----------
    url : str
        The URL in question

    Returns
    -------
    True if headers should be added.
    """
    target_netloc = urllib.parse.urlparse(url).netloc
    configured_netloc = urllib.parse.urlparse(utils.HELP_URL).netloc
    return (
        target_netloc == configured_netloc or
        target_netloc in utils.HELP_HEADERS_HOSTS
    )
