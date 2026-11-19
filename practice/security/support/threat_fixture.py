"""The SandPay merchant portal's threat model, shared by the threat modelling tests and the lesson.

The DFD and attack tree are built from the classes in ``foundations/threat_dfd.py`` and
``foundations/threat_attack_tree.py`` (from ``exercises/`` or ``solutions/``, whichever is on the path).
The data classes are given in the exercise files, so this module imports before anything is solved.
Costs in the attack tree are illustrative effort points, like the values in Schneier's figures.
"""

from __future__ import annotations

from foundations.threat_attack_tree import Node
from foundations.threat_dfd import Boundary, Dfd, Element


def sandpay_dfd(with_log_review: bool = True) -> Dfd:
    """The portal as a DFD. ``with_log_review=False`` is the first draft, whose access log is never read."""
    elements = [
        Element("merchant", "Merchant (browser or API client)", "interactor"),
        Element("ops", "SandPay ops staff", "interactor"),
        Element("receiver", "Merchant webhook receiver", "interactor"),
        Element("portal", "Portal web app and API", "process"),
        Element("db", "Portal database", "data_store"),
        Element("log", "Access log", "data_store"),
        Element("f1", "Login, API calls and form posts", "data_flow", "merchant", "portal"),
        Element("f2", "Pages, JSON and session cookie", "data_flow", "portal", "merchant"),
        Element("f3", "Admin requests", "data_flow", "ops", "portal"),
        Element("f4", "Queries and updates", "data_flow", "portal", "db"),
        Element("f5", "Rows", "data_flow", "db", "portal"),
        Element("f6", "Access log lines", "data_flow", "portal", "log"),
        Element("f7", "Webhook test request", "data_flow", "portal", "receiver"),
    ]
    network = {"portal", "db", "log"}
    if with_log_review:
        elements[4:4] = [Element("review", "Log review", "process")]
        elements += [
            Element("f8", "Log lines", "data_flow", "log", "review"),
            Element("f9", "Alerts and reports", "data_flow", "review", "ops"),
        ]
        network.add("review")
    return Dfd(elements, [Boundary("SandPay network", frozenset(network)), Boundary("Database server", frozenset({"db"}))])


def sandpay_attack_tree() -> Node:
    """Goal: read another merchant's payment data. Leaves name the portal flaw they rely on, if any."""
    return Node("Read another merchant's payment data", "or", [
        Node("Request another merchant's payment by id", cost=10, flaw="idor"),
        Node("Forge an unsigned ops token", cost=20, flaw="jwt-none"),
        Node("Inject SQL into the status filter", cost=40, flaw="sqli"),
        Node("Take over an ops account by guessing", "and", [
            Node("Find an ops email address", cost=10),
            Node("Guess without being throttled", cost=30, flaw="no-rate-limit"),
            Node("The ops password is a common one", cost=60),
        ]),
        Node("Capture traffic on the merchant's network", cost=300, equipment=True),
        Node("Bribe a SandPay insider", cost=5000),
    ])
