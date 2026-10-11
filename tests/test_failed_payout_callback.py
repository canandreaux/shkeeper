import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from flask import Flask

from shkeeper import callback, db
from shkeeper.models import Notification, Payout, PayoutStatus, PayoutTx


@pytest.fixture
def app(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        ENABLE_PAYOUT_CALLBACK=True,
    )
    db.init_app(app)
    monkeypatch.setattr(callback.Crypto, "instances", {})
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def payout(status=PayoutStatus.FAIL, callback_url="https://merchant.test/callback"):
    record = Payout(
        amount=Decimal("12.5"), crypto="USDT", dest_addr="destination",
        status=status, external_id="withdrawal-1", callback_url=callback_url,
        error="Wallet balance is less than payout amount",
        created_at=datetime.utcnow() - timedelta(days=5),
    )
    db.session.add(record)
    db.session.commit()
    return record


@pytest.mark.parametrize("status_code", [200, 202])
def test_failure_without_tx_is_delivered_once(app, monkeypatch, status_code):
    record = payout()
    post = Mock(return_value=Mock(status_code=status_code))
    rate = Mock(side_effect=AssertionError("Failure must not need an exchange rate"))
    monkeypatch.setattr(callback.requests, "post", post)
    monkeypatch.setattr(callback.ExchangeRate, "get", rate)
    callback.queue_failed_payout_notifications()
    callback.queue_failed_payout_notifications()
    assert Notification.query.count() == 1
    notif = Notification.query.one()
    assert callback.send_payout_notification(notif)
    assert callback.send_payout_notification(notif)
    post.assert_called_once()
    body = json.loads(post.call_args.kwargs["data"])
    assert body["status"] == "FAIL"
    assert body["external_id"] == record.external_id
    assert body["tx_hash"] is None
    assert body["error"] == record.error
    assert body["amount_fiat"] is None
    assert notif.callback_confirmed


def test_database_status_change_is_detected(app):
    record = payout(PayoutStatus.IN_PROGRESS)
    callback.queue_failed_payout_notifications()
    assert Notification.query.count() == 0
    db.session.execute(db.update(Payout).where(Payout.id == record.id).values(status=PayoutStatus.FAIL))
    db.session.commit()
    callback.queue_failed_payout_notifications()
    assert Notification.query.one().object_id == record.id


@pytest.mark.parametrize("status,url", [
    (PayoutStatus.IN_PROGRESS, "https://merchant.test/callback"),
    (PayoutStatus.SUCCESS, "https://merchant.test/callback"),
    (PayoutStatus.FAIL, None),
    (PayoutStatus.FAIL, ""),
])
def test_ineligible_records_are_not_queued(app, status, url):
    payout(status, url)
    callback.queue_failed_payout_notifications()
    assert Notification.query.count() == 0


def test_disabled_callbacks_do_not_queue_or_send(app, monkeypatch):
    payout()
    app.config["ENABLE_PAYOUT_CALLBACK"] = False
    post = Mock()
    monkeypatch.setattr(callback.requests, "post", post)
    callback.send_payout_callback_notifier()
    assert Notification.query.count() == 0
    post.assert_not_called()


@pytest.mark.parametrize("network_error", [False, True])
def test_delivery_failure_counts_one_retry(app, monkeypatch, network_error):
    payout()
    callback.queue_failed_payout_notifications()
    notif = Notification.query.one()
    notif.created_at = datetime.utcnow() - timedelta(minutes=10)
    db.session.commit()
    post = Mock(return_value=Mock(status_code=500, reason="Server Error"))
    if network_error:
        post.side_effect = callback.requests.exceptions.Timeout("timeout")
    monkeypatch.setattr(callback.requests, "post", post)
    callback.send_payout_callback_notifier()
    assert notif.retries == 1
    assert not notif.callback_confirmed
    notif.retries = 10
    db.session.commit()
    callback.send_payout_callback_notifier()
    assert post.call_count == 1


def test_success_payload_remains_compatible(app, monkeypatch):
    record = payout(PayoutStatus.SUCCESS)
    db.session.add(PayoutTx(payout_id=record.id, txid="hash"))
    notif = Notification(type="Payout", object_id=record.id, callback_url=record.callback_url)
    db.session.add(notif)
    db.session.commit()
    monkeypatch.setattr(callback.ExchangeRate, "get", Mock(return_value=Mock(get_rate=lambda: Decimal("1"))))
    post = Mock(return_value=Mock(status_code=200))
    monkeypatch.setattr(callback.requests, "post", post)
    assert callback.send_payout_notification(notif)
    body = json.loads(post.call_args.kwargs["data"])
    assert body["status"] == "SUCCESS"
    assert body["tx_hash"] == "hash"
    assert Decimal(body["amount_fiat"]) == Decimal("12.5")
    assert "error" not in body


def test_changed_back_to_pending_is_not_reported_as_failure(app, monkeypatch):
    record = payout()
    callback.queue_failed_payout_notifications()
    record.status = PayoutStatus.IN_PROGRESS
    db.session.commit()
    post = Mock()
    monkeypatch.setattr(callback.requests, "post", post)
    assert not callback.send_payout_notification(Notification.query.one())
    post.assert_not_called()
