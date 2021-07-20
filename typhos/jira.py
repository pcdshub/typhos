import getpass
import logging
import platform
import socket
import urllib
import urllib.parse
import urllib.request
from typing import Dict

from pydm.exception import raise_to_operator
from qtpy import QtWidgets

import typhos

from . import utils

SYSTEM_UNAME_DICT = dict(platform.uname()._asdict())
logger = logging.getLogger(__name__)


def _failsafe_call(func, *args, value_on_failure=None, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as ex:
        if value_on_failure is None:
            return f'FAILURE: {type(ex).__name__}: {ex}'
        return value_on_failure


class TyphosJiraIssueWidget(QtWidgets.QFrame):
    _encoding = "utf-8"

    def __init__(self, device=None, parent=None):
        super().__init__(parent=parent)

        layout = QtWidgets.QFormLayout()
        layout.setFieldGrowthPolicy(layout.AllNonFixedFieldsGrow)
        self.setLayout(layout)

        self._submitted = False

        self.name = QtWidgets.QLineEdit(getpass.getuser())
        layout.addRow("Your &name", self.name)
        # TODO jira suffix
        self.email = QtWidgets.QLineEdit(
            f"{getpass.getuser()}{utils.JIRA_EMAIL_SUFFIX}"
        )
        layout.addRow("Your &e-mail", self.email)
        self.summary = QtWidgets.QLineEdit("")
        layout.addRow("Issue &summary", self.summary)
        self.details = QtWidgets.QPlainTextEdit("""\
* What were you trying to do?

* What did the device/interface/etc do?

* What should have happened?

* Please provide additional context here:
        """.strip())

        layout.addRow("Issue &details", self.details)
        self.submit = QtWidgets.QPushButton("Submit")
        layout.addRow(self.submit)
        self.submit.clicked.connect(self._check_submission)
        self.status = QtWidgets.QLabel()
        layout.addRow(self.status)

        self.device = device
        if device is not None:
            self.summary.setText(
                f"Device {device.name} ({device.__class__.__name__})"
            )

    @staticmethod
    def get_environment():
        """Get the default environment information."""
        env = dict(
            typhos=typhos.__version__,
            user=getpass.getuser(),
            hostname=_failsafe_call(socket.getfqdn),
            **SYSTEM_UNAME_DICT,
        )
        return "\n".join(f"{key}: {value}" for key, value in env.items())

    @property
    def anything_provided(self) -> bool:
        """Were any fields filled out whatsoever?"""
        return any(
            bool(value.strip())
            for value in self.get_dictionary().values()
        )

    def get_dictionary(self, full=False) -> Dict[str, str]:
        """Return all issue details as a dictionary."""
        auto_generated = dict(
            environment=self.get_environment(),
            priority="4",
            webInfo="",
            issueType="1",
        )
        return dict(
            fullname=self.name.text().strip(),
            email=self.email.text().strip(),
            summary=self.summary.text().strip(),
            description=self.details.toPlainText().strip(),
            **(auto_generated if full else {})
        )

    def _check_submission(self):
        as_dict = self.get_dictionary(full=True)
        required_fields = dict(
            fullname="Full name",
            summary="Summary",
            description="Description",
        )
        errors = [
            f"Missing field: {desc}"
            for key, desc in required_fields.items()
            if not as_dict[key]
        ]

        if errors:
            self.status.setText("\n".join(errors))
            return

        print()
        print("---- Issue report ----")
        for key, value in self.get_dictionary(full=True).items():
            text_lines = str(value).splitlines() or [""]
            print(f"{key}: {text_lines[0]}")
            for line in text_lines[1:]:
                print(f"    {line}")
        print()

        self.status.setText("All fields OK. Submitting...")
        try:
            with urllib.request.urlopen(self.request, timeout=5) as fp:
                logger.info(
                    "Jira collector response: %s",
                    fp.read().decode('utf-8')
                )
        except Exception as ex:
            # Sorry, please don't hold it against us...
            raise_to_operator(ex)
            self.status.setText(f"{ex.__class__.__name__} {ex}")
        else:
            self._submitted = True
            self.close()

    @property
    def request(self) -> urllib.request.Request:
        """The submission request."""
        data = self.get_dictionary(full=True)
        return urllib.request.Request(
            utils.JIRA_URL,
            data=urllib.parse.urlencode(data).encode(self._encoding),
            headers=utils.JIRA_HEADERS,
            method="POST",
        )

    def closeEvent(self, event):
        if self._submitted or not self.anything_provided:
            event.accept()
            return

        result = QtWidgets.QMessageBox.question(
            self,
            'Cancel issue submission',
            'Cancel issue submission? Nothing will be saved or reported.',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if result == QtWidgets.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()
