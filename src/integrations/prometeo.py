"""Prometeo Open Banking API client.

Connects to Prometeo's banking API to pull real account data, transactions,
and credit card movements from banks in UY, AR, and LATAM.

Docs: https://docs.prometeoapi.com/reference

Usage:
    client = PrometeoClient(api_key="your-key")
    session = client.login(provider="brou_uy", username="...", password="...")
    accounts = client.get_accounts(session.key)
    movements = client.get_movements(session.key, account_number="...", date_start="01/01/2025", date_end="31/03/2025")
"""

from __future__ import annotations

from datetime import datetime, date
from enum import StrEnum
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger("integrations.prometeo")


# ═══════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════


class LoginStatus(StrEnum):
    LOGGED_IN = "logged_in"
    SELECT_CLIENT = "select_client"
    INTERACTION_REQUIRED = "interaction_required"
    WRONG_CREDENTIALS = "wrong_credentials"
    MISSING_CREDENTIALS = "missing_credentials"


class PrometeoSession(BaseModel):
    status: LoginStatus
    key: str = ""
    provider: str = ""
    logged_in_at: datetime = Field(default_factory=datetime.utcnow)


class PrometeoAccount(BaseModel):
    id: str = ""
    name: str = ""
    number: str = ""
    branch: str = ""
    currency: str = ""
    balance: float = 0.0


class PrometeoMovement(BaseModel):
    id: str = ""
    reference: str = ""
    date: str = ""
    detail: str = ""
    debit: float = 0.0
    credit: float = 0.0
    extra_data: dict[str, Any] = Field(default_factory=dict)


class PrometeoCreditCard(BaseModel):
    id: str = ""
    name: str = ""
    number: str = ""
    close_date: str = ""
    due_date: str = ""
    balance_local: float = 0.0
    balance_dollar: float = 0.0


class PrometeoProvider(BaseModel):
    code: str = ""
    name: str = ""
    country: str = ""


class PrometeoPersonalInfo(BaseModel):
    document: str = ""
    name: str = ""
    email: str = ""


class PrometeoTransferLog(BaseModel):
    request_id: str = ""
    origin_account: str = ""
    destination_account: str = ""
    destination_name: str = ""
    currency: str = ""
    amount: float = 0.0
    status: str = ""  # CREATED, START_CONFIRM, CONFIRMED, ERROR, REJECTED
    created_at: str = ""


# ═══════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════


class PrometeoClient:
    """Client for Prometeo Open Banking API."""

    def __init__(
        self,
        api_key: str,
        sandbox: bool = True,
    ) -> None:
        self.api_key = api_key
        self.base_url = (
            "https://banking.sandbox.prometeoapi.com"
            if sandbox
            else "https://banking.prometeoapi.net"
        )
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={"X-API-Key": api_key},
            timeout=30.0,
        )
        logger.info("prometeo_client_init", base_url=self.base_url, sandbox=sandbox)

    def close(self) -> None:
        self._http.close()

    # ── Auth ──

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    def login(
        self,
        provider: str,
        username: str,
        password: str,
        account_type: str | None = None,
    ) -> PrometeoSession:
        """Login to a banking provider. Returns session key for subsequent calls."""
        data = {"provider": provider, "username": username, "password": password}
        if account_type:
            data["type"] = account_type

        resp = self._http.post("/login/", data=data)
        resp.raise_for_status()
        body = resp.json()

        session = PrometeoSession(
            status=body.get("status", "error"),
            key=body.get("key", ""),
            provider=provider,
        )

        logger.info("prometeo_login", provider=provider, status=session.status)
        return session

    def logout(self, session_key: str) -> bool:
        resp = self._http.get("/logout/", params={"key": session_key})
        return resp.json().get("status") == "logged_out"

    def login_procedure(
        self,
        session_key: str,
        answers: dict[str, str] | None = None,
        otp: str | None = None,
    ) -> PrometeoSession:
        """Handle 2FA / security questions."""
        data: dict[str, str] = {}
        if answers:
            for i, (qid, answer) in enumerate(answers.items(), 1):
                data[f"question_{['one','two','three'][i-1]}_id"] = qid
                data[f"answer_{['one','two','three'][i-1]}"] = answer
        if otp:
            data["otp"] = otp

        resp = self._http.post("/login-procedure/", data=data, params={"key": session_key})
        resp.raise_for_status()
        body = resp.json()
        return PrometeoSession(status=body.get("status", "error"), key=body.get("key", session_key))

    # ── Data ──

    def get_personal_info(self, session_key: str) -> PrometeoPersonalInfo:
        """Get account holder's personal info."""
        resp = self._http.get("/info/", params={"key": session_key})
        resp.raise_for_status()
        info = resp.json().get("info", {})
        return PrometeoPersonalInfo(
            document=info.get("document", ""),
            name=info.get("name", ""),
            email=info.get("email", ""),
        )

    def get_accounts(self, session_key: str) -> list[PrometeoAccount]:
        """Get all accounts for the logged-in user."""
        resp = self._http.get("/account/", params={"key": session_key})
        resp.raise_for_status()
        accounts = resp.json().get("accounts", [])
        return [
            PrometeoAccount(
                id=a.get("id", ""),
                name=a.get("name", ""),
                number=a.get("number", ""),
                branch=a.get("branch", ""),
                currency=a.get("currency", ""),
                balance=float(a.get("balance", 0)),
            )
            for a in accounts
        ]

    def get_movements(
        self,
        session_key: str,
        account_number: str,
        currency: str,
        date_start: str,
        date_end: str,
    ) -> list[PrometeoMovement]:
        """Get account movements. Dates in DD/MM/YYYY format."""
        resp = self._http.get(
            f"/account/{account_number}/movement/",
            params={
                "key": session_key,
                "currency": currency,
                "date_start": date_start,
                "date_end": date_end,
            },
        )
        resp.raise_for_status()
        movements = resp.json().get("movements", [])
        return [
            PrometeoMovement(
                id=m.get("id", ""),
                reference=m.get("reference", ""),
                date=m.get("date", ""),
                detail=m.get("detail", ""),
                debit=float(m.get("debit", 0)),
                credit=float(m.get("credit", 0)),
                extra_data={k: v for k, v in m.items() if k not in ("id", "reference", "date", "detail", "debit", "credit")},
            )
            for m in movements
        ]

    def get_credit_cards(self, session_key: str) -> list[PrometeoCreditCard]:
        """Get credit cards."""
        resp = self._http.get("/credit-card/", params={"key": session_key})
        resp.raise_for_status()
        cards = resp.json().get("credit_cards", [])
        return [
            PrometeoCreditCard(
                id=c.get("id", ""),
                name=c.get("name", ""),
                number=c.get("number", ""),
                close_date=c.get("close_date", ""),
                due_date=c.get("due_date", ""),
                balance_local=float(c.get("balance_local", 0)),
                balance_dollar=float(c.get("balance_dollar", 0)),
            )
            for c in cards
        ]

    def get_credit_card_movements(
        self,
        session_key: str,
        card_number: str,
        currency: str,
        date_start: str,
        date_end: str,
    ) -> list[PrometeoMovement]:
        """Get credit card movements."""
        resp = self._http.get(
            f"/credit-card/{card_number}/movements",
            params={"key": session_key, "currency": currency, "date_start": date_start, "date_end": date_end},
        )
        resp.raise_for_status()
        return [
            PrometeoMovement(
                id=m.get("id", ""),
                reference=m.get("reference", ""),
                date=m.get("date", ""),
                detail=m.get("detail", ""),
                debit=float(m.get("debit", 0)),
                credit=float(m.get("credit", 0)),
            )
            for m in resp.json().get("movements", [])
        ]

    # ── Providers ──

    def list_providers(self, country: str | None = None) -> list[PrometeoProvider]:
        """List available banking providers, optionally filtered by country."""
        resp = self._http.get("/provider/")
        resp.raise_for_status()
        providers = resp.json().get("providers", [])
        result = [
            PrometeoProvider(code=p.get("code", ""), name=p.get("name", ""), country=p.get("country", ""))
            for p in providers
        ]
        if country:
            result = [p for p in result if p.country.upper() == country.upper()]
        return result

    def get_provider_detail(self, provider_code: str) -> dict:
        """Get provider details including auth fields."""
        resp = self._http.get(f"/provider/{provider_code}/")
        resp.raise_for_status()
        return resp.json()

    # ── Clients (multi-company) ──

    def get_clients(self, session_key: str) -> dict[str, str]:
        """Get available clients (for multi-company providers)."""
        resp = self._http.get("/client/", params={"key": session_key})
        resp.raise_for_status()
        return resp.json().get("clients", {})

    def select_client(self, session_key: str, client_id: str) -> bool:
        """Select a specific client for multi-company sessions."""
        resp = self._http.get(f"/client/{client_id}/", params={"key": session_key})
        return resp.json().get("status") == "success"

    # ── Transfers ──

    # ── Transfers: Destinations & Form Fields ──

    def get_transfer_destinations(self, session_key: str) -> list[dict]:
        """List institutions available as transfer destinations."""
        resp = self._http.get("/transfer/destinations/", params={"key": session_key})
        resp.raise_for_status()
        return resp.json().get("destinations", [])

    def get_transfer_form_fields(self, session_key: str) -> list[dict]:
        """Get required form fields for transfers (varies by provider)."""
        resp = self._http.get("/transfer/form-fields", params={"key": session_key})
        resp.raise_for_status()
        return resp.json().get("transfer_form_fields", [])

    def get_transfer_mfa_methods(self, session_key: str) -> list[str]:
        """Get available MFA methods required to confirm transfers."""
        resp = self._http.get("/transfer/mfa-methods", params={"key": session_key})
        resp.raise_for_status()
        return resp.json().get("authorization_devices", [])

    # ── Transfers: Account Enrollment ──

    def get_enroll_form_fields(self, session_key: str) -> list[dict]:
        """Get required fields for pre-enrolling a destination account."""
        resp = self._http.get("/transfer/account-enroll-form", params={"key": session_key})
        resp.raise_for_status()
        return resp.json().get("account_enroll_fields", [])

    def enroll_account(
        self,
        session_key: str,
        destination_institution: str,
        destination_account: str,
        destination_owner_name: str,
        currency: str | None = None,
        account_type: str | None = None,
        document_number: str | None = None,
        document_type: str | None = None,
        authorization_data: str | None = None,
        enroll_authorization_data: str | None = None,
    ) -> dict:
        """Pre-enroll a destination account for transfers."""
        data = {
            "destination_institution": destination_institution,
            "destination_account": destination_account,
            "destination_owner_name": destination_owner_name,
        }
        for k, v in [("currency", currency), ("account_type", account_type),
                      ("document_number", document_number), ("document_type", document_type),
                      ("authorization_data", authorization_data),
                      ("enroll_authorization_data", enroll_authorization_data)]:
            if v:
                data[k] = v

        resp = self._http.post("/transfer/account-enroll", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()

    def confirm_enrollment(self, session_key: str, request_id: str, authorization_data: str) -> dict:
        """Confirm account enrollment when subsequent authorization is required."""
        resp = self._http.post(
            "/transfer/account-enroll-confirm",
            data={"request_id": request_id, "authorization_data": authorization_data},
            params={"key": session_key},
        )
        resp.raise_for_status()
        return resp.json()

    def remove_enrollment(
        self,
        session_key: str,
        destination_account: str,
        destination_institution: str | None = None,
        authorization_data: str | None = None,
    ) -> dict:
        """Remove a pre-enrolled destination account."""
        data: dict[str, str] = {"destination_account": destination_account}
        if destination_institution:
            data["destination_institution"] = destination_institution
        if authorization_data:
            data["authorization_data"] = authorization_data
        resp = self._http.post("/transfer/account-enroll-remove", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()

    # ── Transfers: Preprocess & Confirm ──

    def preprocess_transfer(
        self,
        session_key: str,
        origin_account: str,
        destination_institution: int | str,
        destination_account: str,
        currency: str,
        amount: float,
        concept: str,
        destination_owner_name: str | None = None,
        branch: int | str | None = None,
        destination_account_type: str | None = None,
        document_number: str | None = None,
        document_type: str | None = None,
        reason: str | None = None,
        origin_holder: str | None = None,
        origin_cuit: str | None = None,
        origin_cvu: str | None = None,
        destination_cuit: str | None = None,
    ) -> dict:
        """Preprocess a transfer. Returns request_id + authorization_devices for confirmation.

        Returns: {status, result: {approved, request_id, authorization_devices, message}}
        """
        data: dict[str, Any] = {
            "origin_account": origin_account,
            "destination_institution": str(destination_institution),
            "destination_account": destination_account,
            "currency": currency,
            "amount": str(amount),
            "concept": concept,
        }
        for k, v in [("destination_owner_name", destination_owner_name), ("branch", branch),
                      ("destination_account_type", destination_account_type),
                      ("document_number", document_number), ("document_type", document_type),
                      ("reason", reason), ("origin_holder", origin_holder),
                      ("origin_cuit", origin_cuit), ("origin_cvu", origin_cvu),
                      ("destination_cuit", destination_cuit)]:
            if v is not None:
                data[k] = str(v)

        resp = self._http.post("/transfer/preprocess", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()

    def retry_preprocess_transfer(self, session_key: str, request_id: str) -> dict:
        """Retry a failed preprocess with the same data (Santander UY only)."""
        resp = self._http.post(
            "/transfer/preprocess/retry",
            data={"request_id": request_id},
            params={"key": session_key},
        )
        resp.raise_for_status()
        return resp.json()

    def confirm_transfer(
        self,
        session_key: str,
        request_id: str,
        authorization_type: str | None = None,
        authorization_data: str | None = None,
        authorization_device_number: str | None = None,
    ) -> dict:
        """Confirm a preprocessed transfer.

        Returns: {status, transfer: {success, message}}
        """
        data: dict[str, str] = {"request_id": request_id}
        if authorization_type:
            data["authorization_type"] = authorization_type
        if authorization_data:
            data["authorization_data"] = authorization_data
        if authorization_device_number:
            data["authorization_device_number"] = authorization_device_number

        resp = self._http.post("/transfer/confirm", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()

    def get_transfer_detail(self, session_key: str, request_id: str) -> dict:
        """Get details of a specific transfer (Bancolombia CO only)."""
        resp = self._http.post(
            "/transfer/detail",
            data={"request_id": request_id},
            params={"key": session_key},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Transfers: Logs ──

    def get_transfer_logs(self, date_start: str, date_end: str) -> list[PrometeoTransferLog]:
        """Get all transfer logs across providers. Dates in DD/MM/YYYY."""
        resp = self._http.get(
            "/transfer/logs",
            params={"date_start": date_start, "date_end": date_end},
        )
        resp.raise_for_status()
        logs = resp.json().get("transfers", [])
        return [
            PrometeoTransferLog(
                request_id=t.get("request_id", ""),
                origin_account=t.get("origin_account", ""),
                destination_account=t.get("destination_account", ""),
                destination_name=t.get("destination_name", ""),
                currency=t.get("currency", ""),
                amount=float(t.get("amount", 0)),
                status=t.get("status", ""),
                created_at=t.get("created_at", ""),
            )
            for t in logs
        ]

    def get_transfer_log_detail(self, request_id: str) -> dict:
        """Get details for a specific transfer log entry."""
        resp = self._http.get(f"/transfer/logs/{request_id}")
        resp.raise_for_status()
        return resp.json()

    # ── Transfers: Validation ──

    def validate_account(
        self,
        session_key: str,
        account: str,
        account_type: str | None = None,
        bank_code: str | None = None,
    ) -> dict:
        """Validate a destination account (BROU UY, BBVA Netcash, Interbank PE).

        Returns: {status, result: {valid, message, data: {beneficiary_name, account_currency, ...}}}
        """
        data: dict[str, str] = {"account": account}
        if account_type:
            data["account_type"] = account_type
        if bank_code:
            data["bank_code"] = bank_code
        resp = self._http.post("/transfer/validate-account", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()

    # ── Transfers: Batch (Telecrédito BCP Perú) ──

    def preprocess_batch_transfer(
        self,
        session_key: str,
        data_payload: str,
        format: str = "json",
    ) -> dict:
        """Preprocess a batch of transfers. Format: 'json' or 'base64'.

        Returns: {status, result: {approved, request_id, authorization_devices, declined_payments}}
        """
        resp = self._http.post(
            "/transfer/batch/preprocess",
            data={"data": data_payload, "format": format},
            params={"key": session_key},
        )
        resp.raise_for_status()
        return resp.json()

    def confirm_batch_transfer(
        self,
        session_key: str,
        request_id: str,
        authorization_type: str | None = None,
        authorization_data: str | None = None,
    ) -> dict:
        """Confirm a batch transfer."""
        data: dict[str, str] = {"request_id": request_id}
        if authorization_type:
            data["authorization_type"] = authorization_type
        if authorization_data:
            data["authorization_data"] = authorization_data
        resp = self._http.post("/transfer/batch/confirm", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()

    def get_batch_transfer_detail(
        self,
        session_key: str,
        request_id: str,
        format: str = "csv",
        separator: str | None = None,
    ) -> dict:
        """Get details of a batch transfer. Format: csv, xls, txt.

        Returns: {status, result: {success, file_result: {data, encoded_in, format}, meta}}
        """
        data: dict[str, str] = {"request_id": request_id, "format": format}
        if separator:
            data["separator"] = separator
        resp = self._http.post("/transfer/batch/detail", data=data, params={"key": session_key})
        resp.raise_for_status()
        return resp.json()


# ═══════════════════════════════════════════════
# Ingestion bridge — converts Prometeo data to Sentinel Swarm events
# ═══════════════════════════════════════════════


class PrometeoIngestion:
    """Pulls data from Prometeo and converts to Sentinel Swarm banking events.

    This bridges real bank data into the fraud detection pipeline.
    """

    def __init__(self, client: PrometeoClient) -> None:
        self.client = client

    def sync_account(
        self,
        session_key: str,
        tenant_id: str,
        date_start: str,
        date_end: str,
        api_base: str = "http://localhost:3000",
    ) -> dict[str, Any]:
        """Full sync: pull accounts + movements from Prometeo, push as events to Sentinel Swarm.

        Returns summary of what was ingested.
        """
        http = httpx.Client(base_url=api_base, timeout=60.0)
        summary = {"accounts": 0, "movements": 0, "events_sent": 0, "errors": []}

        try:
            # Get personal info
            info = self.client.get_personal_info(session_key)
            logger.info("prometeo_sync_info", name=info.name, document=info.document)

            # Get accounts
            accounts = self.client.get_accounts(session_key)
            summary["accounts"] = len(accounts)
            logger.info("prometeo_sync_accounts", count=len(accounts))

            for account in accounts:
                # Get movements for each account
                try:
                    movements = self.client.get_movements(
                        session_key,
                        account_number=account.number,
                        currency=account.currency,
                        date_start=date_start,
                        date_end=date_end,
                    )
                    summary["movements"] += len(movements)

                    # Convert each movement to a Sentinel Swarm event
                    for mov in movements:
                        event = self._movement_to_event(
                            movement=mov,
                            account=account,
                            personal_info=info,
                            tenant_id=tenant_id,
                        )

                        # Send to Sentinel Swarm API
                        resp = http.post("/api/events/process", json=event)
                        if resp.status_code < 400:
                            summary["events_sent"] += 1
                        else:
                            summary["errors"].append(f"Event failed: {resp.status_code}")

                except Exception as e:
                    summary["errors"].append(f"Account {account.number}: {str(e)}")
                    logger.error("prometeo_sync_movements_error", account=account.number, error=str(e))

        except Exception as e:
            summary["errors"].append(str(e))
            logger.error("prometeo_sync_error", error=str(e))
        finally:
            http.close()

        logger.info("prometeo_sync_complete", **summary)
        return summary

    def _movement_to_event(
        self,
        movement: PrometeoMovement,
        account: PrometeoAccount,
        personal_info: PrometeoPersonalInfo,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Convert a Prometeo movement to a Sentinel Swarm process event request."""
        is_debit = movement.debit > 0
        amount = movement.debit if is_debit else movement.credit

        return {
            "tenant_id": tenant_id,
            "account_id": account.number,
            "user_id": personal_info.document or account.number,
            "event_type": "transfer",
            "amount": amount,
            "currency": account.currency,
            "destination_account": movement.reference if is_debit else None,
            "document_type": "cedula" if len(personal_info.document) < 12 else "DNI",
            "document_number": personal_info.document,
            "name": personal_info.name,
            "email": personal_info.email,
        }

    def sync_transfer_logs(
        self,
        tenant_id: str,
        date_start: str,
        date_end: str,
        api_base: str = "http://localhost:3000",
    ) -> dict[str, Any]:
        """Pull transfer logs from Prometeo and ingest as events."""
        http = httpx.Client(base_url=api_base, timeout=60.0)
        summary = {"transfers": 0, "events_sent": 0, "errors": []}

        try:
            logs = self.client.get_transfer_logs(date_start, date_end)
            summary["transfers"] = len(logs)

            for log in logs:
                event = {
                    "tenant_id": tenant_id,
                    "account_id": log.origin_account,
                    "user_id": log.origin_account,
                    "event_type": "transfer",
                    "amount": log.amount,
                    "currency": log.currency,
                    "destination_account": log.destination_account,
                    "name": log.destination_name,
                }

                resp = http.post("/api/events/process", json=event)
                if resp.status_code < 400:
                    summary["events_sent"] += 1

        except Exception as e:
            summary["errors"].append(str(e))
        finally:
            http.close()

        return summary
