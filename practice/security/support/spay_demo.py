"""Prints every number and output the payment security lesson shows. Run from practice/security:

    SEC_TARGET=solutions .venv/bin/python support/spay_demo.py

No card number is ever printed in full: values are masked, counted, or described. Nothing leaves the machine.
"""

import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / os.environ.get("SEC_TARGET", "solutions")))
sys.path.insert(1, str(ROOT / "support"))

import spay_fixture as fx  # noqa: E402
from specialised import spay_audit, spay_detect, spay_velocity  # noqa: E402


def heading(text):
    print(f"\n## {text}")


heading("1. masks by PAN length (first 6 + stars + last digits; at least 4 hidden)")
for length in (13, 14, 15, 16, 19):
    digits = fx.make_test_pan("4", length, 1)
    print(f"  {length} digits -> {spay_detect.mask_pan(digits)}  (hidden: {spay_detect.mask_pan(digits).count('*')})")

heading("2. how often does a random 16-digit run pass the Luhn check?")
rng = random.Random(2026)
passed = sum(spay_detect.luhn_valid("".join(str(rng.randrange(10)) for _ in range(16))) for _ in range(100000))
print(f"  {passed} of 100000 random 16-digit runs pass ({passed / 1000:.1f}%)")

heading("3. find_pans / redact on one made-up log line")
pan_a, pan_b = fx.make_test_pan("4", 16, 11), fx.make_test_pan("37", 15, 12)
grouped = "-".join(pan_a[i:i + 4] for i in range(0, 16, 4))
order_id = fx.break_luhn(fx.make_test_pan("9", 16, 13))   # a 16-digit id that fails Luhn: not a card
lucky_id = fx.make_test_pan("9", 16, 14)                   # a 16-digit id that passes Luhn: indistinguishable from a card
line = f"POST /pay card={pan_a} alt={grouped} amex={pan_b} order={order_id} ticket={lucky_id} amount=2500"
print(f"  line length: {len(line)} characters; it holds 5 long numbers: 2 forms of one Visa-like, 1 Amex-like, 2 ids")
for hit in spay_detect.find_pans(line):
    print(f"  hit start={hit.start:3d} end={hit.end:3d} digits={hit.length:2d} masked={hit.masked}")
shown = spay_detect.redact(line).replace(order_id, "<16-digit id, fails Luhn, left alone>")  # replaced only for display here
print(f"  redact(line) -> {shown}")

heading("4. audit_card_data on the default gateway, then one flaw at a time")
print("  default gateway:", spay_audit.audit_card_data(fx.CardGateway()))
print("  fully fixed    :", spay_audit.audit_card_data(fx.CardGateway(fixed=fx.FLAWS)))
for flaw in ("pan-in-response", "pan-in-log", "pan-stored-plain", "cvv-stored", "unmasked-display"):
    gw = fx.CardGateway(fixed=set(fx.FLAWS) - {flaw})
    print(f"  only {flaw:<17} unfixed -> {spay_audit.audit_card_data(gw)}")

heading("5. what the flawed and the fixed gateway wrote (redacted by our own redact())")
for label, gw in (("flawed", fx.CardGateway()), ("fixed ", fx.CardGateway(fixed=fx.FLAWS))):
    card = gw.test_cards[0]
    status, body = gw.authorize("m_100", "demo", card["pan"], card["expiry"], card["cvv"], 1000)
    raw = {"log": gw.log[-1], "response": fx.flat_text(body), "record": str(gw.export_records()[0]), "receipt": gw.receipt(body["payment_id"])}
    print(f"  {label} raw surface holds the full PAN: " + ", ".join(f"{k}={card['pan'] in v}" for k, v in raw.items()))
    print(f"  {label} log     : {spay_detect.redact(gw.log[-1])}")
    print(f"  {label} response: {spay_detect.redact(fx.flat_text(body))}")
    print(f"  {label} record  : keys={sorted(gw.export_records()[0])}")
    print(f"  {label} receipt : {spay_detect.redact(gw.receipt(body['payment_id']))}")
    print(f"  {label} exposed digits on the receipt: {spay_audit.exposed_digits(gw.receipt(body['payment_id']), card['pan'])}")

heading("6. audit_tokens")
print("  default gateway:", spay_audit.audit_tokens(fx.CardGateway()))
print("  fully fixed    :", spay_audit.audit_tokens(fx.CardGateway(fixed=fx.FLAWS)))
for flaw in ("token-guessable", "token-cross-merchant"):
    gw = fx.CardGateway(fixed=set(fx.FLAWS) - {flaw})
    print(f"  only {flaw:<21} unfixed -> {spay_audit.audit_tokens(gw)}")
bad, good = fx.CardGateway(), fx.CardGateway(fixed=fx.FLAWS)
for label, gw in (("flawed", bad), ("fixed ", good)):
    tokens = [gw.tokenize("m_100", c["pan"], c["expiry"])[1]["token"] for c in gw.test_cards]
    shown = [t if label == "flawed" else t[:8] + "..." + t[-4:] for t in tokens]
    print(f"  {label} tokens: {shown}")
    print(f"  {label} merchant m_200 charging m_100's first token -> status {gw.charge_token('m_200', tokens[0], 100)[0]}")

heading("7. detect_card_testing on a mixed stream of synthetic events")
events = []
events += fx.shopper_events("ip_a", 0, 12) + fx.shopper_events("ip_b", 90, 12) + fx.shopper_events("ip_c", 200, 12)
events += fx.busy_merchant_events("m_100", 300, 120)
events += fx.tester_events("ip_x", 1000, 40)
events += fx.tester_events("ip_slow", 0, 40, step=20)
print(f"  {len(events)} events, {len({e['client'] for e in events})} clients")
for s in spay_velocity.detect_card_testing(events):
    print(f"  suspect {s}")
print("  ip_slow with a 60 s window  :", [s.client for s in spay_velocity.detect_card_testing(events) if s.client == "ip_slow"] or "not found")
longer = [s for s in spay_velocity.detect_card_testing(events, window_s=300) if s.client == "ip_slow"]
print("  ip_slow with a 300 s window :", longer)
only_busy = spay_velocity.detect_card_testing(fx.busy_merchant_events("m_100", 0, 120))
print("  busy merchant alone         :", only_busy)

heading("8. probe_velocity_limit")
print("  default gateway   :", spay_velocity.probe_velocity_limit(fx.CardGateway(), max_attempts=30))
fixed = fx.CardGateway(fixed={"no-velocity"})
print("  no-velocity fixed :", spay_velocity.probe_velocity_limit(fixed, client="shared-ip"))
card = fixed.test_cards[0]
print("  then a real card from the same client ->", fixed.authorize("m_100", "shared-ip", card["pan"], card["expiry"], card["cvv"], 500)[0])
print("  a real card from another client      ->", fixed.authorize("m_100", "other-ip", card["pan"], card["expiry"], card["cvv"], 500)[0])
