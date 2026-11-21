"""Synthetic source for the SAST and secret-scanning lesson (prefix sast_).

Everything here is made up. SandPay is fictional; the keys below were never issued by anyone. The Python
snippets are written to be PARSED, never run.
"""

from __future__ import annotations

from pathlib import Path

PORTAL_SOURCE = Path(__file__).with_name("sandpay_vuln.py")

# One flaw per function, each the shape a rule should find.
VULNERABLE_HANDLERS = '''\
import hashlib
import subprocess

import requests


def search_fstring(db, status):
    return db.execute(f"SELECT * FROM payments WHERE status = '{status}'")


def search_concat(db, status):
    return db.execute("SELECT * FROM payments WHERE status = '" + status + "'")


def search_format(db, status):
    return db.execute("SELECT * FROM payments WHERE status = '{}'".format(status))


def search_percent(db, status):
    return db.execute("SELECT * FROM payments WHERE status = '%s'" % status)


def calculate(expression):
    return eval(expression)


def ping(host):
    return subprocess.run("ping -c 1 " + host, shell=True)


def fingerprint_password(password):
    return hashlib.md5(password.encode()).hexdigest()


def fetch(url):
    return requests.get(url, verify=False)
'''

# The same functions with each flaw fixed, plus code that LOOKS risky but is fine.
FIXED_HANDLERS = '''\
import ast
import hashlib
import subprocess

import requests

BY_STATUS = "SELECT * FROM payments WHERE status = ?"
TWO_PARTS = "SELECT id FROM payments " + "WHERE status = 'paid'"


def search(db, status):
    return db.execute(BY_STATUS, (status,))


def search_literal(db):
    return db.execute("SELECT * FROM payments WHERE status = ?", ("paid",))


def search_constant_concat(db):
    return db.execute("SELECT id FROM payments " + "WHERE status = 'paid'")


def calculate(expression):
    return ast.literal_eval(expression)


def ping(host):
    return subprocess.run(["ping", "-c", "1", host], check=True)


def checksum(blob):
    return hashlib.sha1(blob, usedforsecurity=False).hexdigest()


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex()


def fetch(url):
    return requests.get(url, timeout=5)
'''

# What the secret scanner should (and should not) report. Line numbers are asserted by the tests.
SETTINGS_FILE = '''\
SANDPAY_KEY = "sp_live_Zk3pQ9vL2mXa7TdRw4Ns8BhY"
DB_PASSWORD = "r7Q!mZ2x#Lw9vKp4"
api_key = "YOUR_API_KEY_HERE"
password = "changeme-changeme"
WEBHOOK_TOKEN = "Zk3pQ9vL2mXa7TdRw4Ns8BhY"  # scanner:allow
retry_token_header = "X-Retry-Token"
timeout = "30000000"
-----BEGIN PRIVATE KEY-----
'''
