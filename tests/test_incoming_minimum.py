from decimal import Decimal
from unittest.mock import Mock

import pytest
from flask import Flask

from shkeeper import api_v1


@pytest.fixture
def notify(monkeypatch):
    app = Flask(__name__)
    app.config["UNCONFIRMED_TX_NOTIFICATION"] = True
    monkeypatch.setenv("SHKEEPER_BTC_BACKEND_KEY", "test-backend")
    crypto = Mock()
    tx = Mock(need_more_confirmations=False)
    add = Mock(return_value=tx)
    unconfirmed = Mock()
    outgoing = Mock()
    callback = Mock()
    unconfirmed_callback = Mock()
    monkeypatch.setattr(api_v1.Transaction, "add", add)
    monkeypatch.setattr(api_v1.Transaction, "add_outgoing", outgoing)
    monkeypatch.setattr(api_v1.UnconfirmedTransaction, "add", unconfirmed)
    monkeypatch.setattr(api_v1.UnconfirmedTransaction, "delete", Mock())
    monkeypatch.setattr(api_v1, "send_notification_async", callback)
    monkeypatch.setattr(api_v1, "send_unconfirmed_notification_async", unconfirmed_callback)

    def run(symbol, amount, confirmations=1, category="receive", minimum=None):
        crypto.crypto = symbol
        crypto.getaddrbytx.return_value = [("address", Decimal(amount), confirmations, category)]
        monkeypatch.setattr(api_v1.Crypto, "instances", {symbol: crypto})
        if minimum is not None:
            app.config[f"{symbol}_MIN_INCOMING_AMOUNT"] = minimum
        with app.test_request_context(headers={"X-Shkeeper-Backend-Key": "test-backend"}):
            assert api_v1.walletnotify(symbol, "txid") == {"status": "success"}
        return add, unconfirmed, outgoing, callback, unconfirmed_callback, tx

    return run


@pytest.mark.parametrize("symbol", ["TRX", "USDT"])
@pytest.mark.parametrize("amount", ["0.000001", "0.099999"])
@pytest.mark.parametrize("confirmations", [0, 1])
def test_small_payments_do_not_create_records_or_callbacks(notify, symbol, amount, confirmations):
    add, unconfirmed, outgoing, callback, unconfirmed_callback, tx = notify(symbol, amount, confirmations)
    for action in (add, unconfirmed, outgoing, callback, unconfirmed_callback, tx.invoice.update_with_tx):
        action.assert_not_called()


@pytest.mark.parametrize("symbol", ["TRX", "USDT"])
@pytest.mark.parametrize("amount", ["0.1", "0.100001"])
def test_boundary_and_larger_payments_are_processed(notify, symbol, amount):
    add, _, _, callback, _, tx = notify(symbol, amount)
    add.assert_called_once()
    tx.invoice.update_with_tx.assert_called_once_with(tx)
    callback.assert_called_once_with(tx)


def test_other_tokens_are_not_filtered(notify):
    add, *_ = notify("ETH-USDT", "0.000001")
    add.assert_called_once()


def test_small_outgoing_transfer_is_not_filtered(notify):
    add, unconfirmed, outgoing, *_ = notify("TRX", "0.000001", category="send")
    outgoing.assert_called_once()
    add.assert_not_called()
    unconfirmed.assert_not_called()


def test_minimum_is_configurable(notify):
    add, *_ = notify("USDT", "0.01", minimum="0.01")
    add.assert_called_once()
