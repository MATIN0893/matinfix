from app.accounting.mode import AccountantMode
from app.agents.core import MatinAICore
from app.agents.registry import AgentName


def test_only_exact_nss_enters_admin_mode() -> None:
    core = MatinAICore(accountant=AccountantMode())
    assert core.route_role("NSS") is AgentName.ADMIN
    assert core.route_role("NSS please") is AgentName.CUSTOMER
    assert core.route_role("нсс") is AgentName.CUSTOMER


def test_non_nss_message_cannot_return_accountant_report() -> None:
    core = MatinAICore(accountant=AccountantMode())
    result = core.handle_admin("доход 5000")
    assert result.agent is AgentName.CUSTOMER
    assert result.response == ""
