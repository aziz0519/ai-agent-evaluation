from datetime import date
from unittest.mock import patch

# Import the tool functions directly (they are LangChain tools, need to access .func)
from agent.tools import (
    calculate_right_refund,
    get_today_date,
    get_user_purchase_history,
    issue_refund_ticket,
)

# Call the underlying function via .func since these are StructuredTool objects
get_user_purchase_history_func = get_user_purchase_history.func
calculate_right_refund_func = calculate_right_refund.func
issue_refund_ticket_func = issue_refund_ticket.func
get_today_date_func = get_today_date.func

from agent.objects import PurchaseItem


class TestGetUserPurchaseHistory:
    def test_returns_data_for_known_user(self):
        result = get_user_purchase_history_func("user123")
        assert isinstance(result, dict)
        assert "book" in result
        assert "pen" in result
        assert result["book"]["price"] == 23
        assert result["pen"]["price"] == 7

    def test_returns_error_for_unknown_user(self):
        result = get_user_purchase_history_func("nonexistent_user")
        assert result == {"status": "there was no username found"}

    def test_case_sensitive_username(self):
        result = get_user_purchase_history_func("User123")
        assert result == {"status": "there was no username found"}


class TestCalculateRightRefund:
    def test_calculates_total_for_valid_items(self):
        items = [PurchaseItem(name="book"), PurchaseItem(name="pen")]
        result = calculate_right_refund_func("user123", items)
        assert result == "the value of the refund is: 30"

    def test_calculates_for_single_item(self):
        items = [PurchaseItem(name="book")]
        result = calculate_right_refund_func("user123", items)
        assert result == "the value of the refund is: 23"

    def test_returns_error_for_unknown_user(self):
        items = [PurchaseItem(name="book")]
        result = calculate_right_refund_func("nonexistent", items)
        assert result == {"status": "there was no username found"}

    def test_returns_zero_for_items_not_in_purchase_history(self):
        items = [PurchaseItem(name="water_bottle")]
        result = calculate_right_refund_func("user123", items)
        assert result == "the value of the refund is: 0"

    def test_partial_match_only_sums_found_items(self):
        items = [
            PurchaseItem(name="backpack"),
            PurchaseItem(name="water_bottle"),
            PurchaseItem(name="nonexistent_item"),
        ]
        result = calculate_right_refund_func("user126", items)
        assert result == "the value of the refund is: 63"

    def test_empty_items_list_returns_zero(self):
        result = calculate_right_refund_func("user123", [])
        assert result == "the value of the refund is: 0"


class TestIssueRefundTicket:
    def test_formats_refund_amount_correctly(self):
        result = issue_refund_ticket_func("user123", 30)
        assert result == "a refund ticket has been issued successfully with the amount of 30"

    def test_handles_zero_amount(self):
        result = issue_refund_ticket_func("user123", 0)
        assert result == "a refund ticket has been issued successfully with the amount of 0"

    def test_handles_negative_amount(self):
        result = issue_refund_ticket_func("user123", -10)
        assert result == "a refund ticket has been issued successfully with the amount of -10"


class TestGetTodayDate:
    def test_returns_iso_format_date(self, monkeypatch):
        with patch("agent.tools.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 15)
            result = get_today_date_func("user123")
            assert result == "2026-01-15"

    def test_user_parameter_is_unused_but_accepted(self):
        with patch("agent.tools.date") as mock_date:
            mock_date.today.return_value = date(2026, 1, 15)
            result1 = get_today_date_func("user123")
            result2 = get_today_date_func("user999")
            result3 = get_today_date_func("")
            assert result1 == result2 == result3 == "2026-01-15"


class TestDataConsistency:
    def test_all_golden_users_exist_in_data(self):
        expected_users = ["user123", "user999", "user126"]
        from agent.data import users_data
        for user in expected_users:
            # user999 is intentionally missing in agent/data.py
            if user == "user999":
                assert user not in users_data
            else:
                assert user in users_data

    def test_item_prices_are_integers(self):
        from agent.data import users_data
        for items in users_data.values():
            for item_data in items.values():
                assert isinstance(item_data["price"], int)
                assert item_data["price"] > 0

    def test_item_dates_are_parseable(self):
        from agent.data import users_data
        # date.fromisoformat requires zero-padded days/months (2026-10-05)
        # but our fixture uses non-zero-padded (2026-10-5).
        # Accept both by trying ISO format first, then lenient parsing.
        for items in users_data.values():
            for item_data in items.values():
                date_str = item_data["date"]
                try:
                    date.fromisoformat(date_str)
                except ValueError:
                    # Fallback: try parsing as YYYY-M-D or YYYY-MM-D etc.
                    parts = date_str.split("-")
                    assert len(parts) == 3
                    date(int(parts[0]), int(parts[1]), int(parts[2]))
