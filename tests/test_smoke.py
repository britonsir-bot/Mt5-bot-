from app import create_app_context


def test_create_app_context_contains_services():
    context = create_app_context()
    assert "settings" in context
    assert "database" in context
    assert "account_service" in context
    assert "order_manager" in context
