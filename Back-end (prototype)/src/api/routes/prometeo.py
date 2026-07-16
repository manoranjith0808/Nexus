"""Prometeo Open Banking integration endpoints.

Allows connecting real bank accounts via Prometeo API to pull
transactions and feed them into the fraud detection pipeline.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sentinel_swarm.config import get_settings
from sentinel_swarm.integrations.prometeo import PrometeoClient, PrometeoIngestion

router = APIRouter()


def _get_client() -> PrometeoClient:
    settings = get_settings()
    api_key = settings.prometeo_api_key
    if not api_key:
        raise HTTPException(400, "PROMETEO_API_KEY not configured. Set it in .env")
    sandbox = settings.prometeo_sandbox
    return PrometeoClient(api_key=api_key, sandbox=sandbox)


# ── Models ──

class LoginRequest(BaseModel):
    provider: str
    username: str
    password: str
    account_type: str | None = None


class SyncRequest(BaseModel):
    session_key: str
    tenant_id: str
    date_start: str  # DD/MM/YYYY
    date_end: str    # DD/MM/YYYY


class LoginProcedureRequest(BaseModel):
    session_key: str
    answers: dict[str, str] | None = None
    otp: str | None = None


# ── Endpoints ──

@router.get("/providers")
async def list_providers(country: str | None = Query(None)):
    """List available banking providers from Prometeo."""
    client = _get_client()
    try:
        providers = client.list_providers(country=country)
        return {"providers": [p.model_dump() for p in providers]}
    finally:
        client.close()


@router.get("/providers/{code}")
async def provider_detail(code: str):
    """Get details for a specific provider (auth fields, logo, etc)."""
    client = _get_client()
    try:
        return client.get_provider_detail(code)
    finally:
        client.close()


@router.post("/login")
async def login(req: LoginRequest):
    """Login to a banking provider via Prometeo.

    Returns a session key for subsequent operations.
    If status is 'interaction_required', call /prometeo/login-procedure with the 2FA data.
    If status is 'select_client', call /prometeo/clients to list and select one.
    """
    client = _get_client()
    try:
        session = client.login(
            provider=req.provider,
            username=req.username,
            password=req.password,
            account_type=req.account_type,
        )
        return session.model_dump()
    finally:
        client.close()


@router.post("/login-procedure")
async def login_procedure(req: LoginProcedureRequest):
    """Handle 2FA / security questions for Prometeo login."""
    client = _get_client()
    try:
        session = client.login_procedure(
            session_key=req.session_key,
            answers=req.answers,
            otp=req.otp,
        )
        return session.model_dump()
    finally:
        client.close()


@router.get("/accounts")
async def get_accounts(session_key: str = Query(...)):
    """Get all accounts for a logged-in Prometeo session."""
    client = _get_client()
    try:
        accounts = client.get_accounts(session_key)
        return {"accounts": [a.model_dump() for a in accounts]}
    finally:
        client.close()


@router.get("/accounts/{account_number}/movements")
async def get_movements(
    account_number: str,
    session_key: str = Query(...),
    currency: str = Query(...),
    date_start: str = Query(..., description="DD/MM/YYYY"),
    date_end: str = Query(..., description="DD/MM/YYYY"),
):
    """Get movements for a specific account."""
    client = _get_client()
    try:
        movements = client.get_movements(
            session_key=session_key,
            account_number=account_number,
            currency=currency,
            date_start=date_start,
            date_end=date_end,
        )
        return {"movements": [m.model_dump() for m in movements], "count": len(movements)}
    finally:
        client.close()


@router.get("/credit-cards")
async def get_credit_cards(session_key: str = Query(...)):
    """Get credit cards for a logged-in session."""
    client = _get_client()
    try:
        cards = client.get_credit_cards(session_key)
        return {"credit_cards": [c.model_dump() for c in cards]}
    finally:
        client.close()


@router.get("/info")
async def get_personal_info(session_key: str = Query(...)):
    """Get personal info for the logged-in user."""
    client = _get_client()
    try:
        info = client.get_personal_info(session_key)
        return info.model_dump()
    finally:
        client.close()


@router.get("/clients")
async def get_clients(session_key: str = Query(...)):
    """Get available clients for multi-company sessions."""
    client = _get_client()
    try:
        return client.get_clients(session_key)
    finally:
        client.close()


@router.post("/sync")
async def sync_account(req: SyncRequest):
    """Full sync: pull all accounts + movements from Prometeo and feed into Sentinel Swarm pipeline.

    This is the main integration point — it:
    1. Pulls accounts from the bank via Prometeo
    2. Pulls movements for each account
    3. Converts each movement to a banking event
    4. Sends each event through the 6-agent fraud detection pipeline

    Use this after a successful /prometeo/login.
    """
    client = _get_client()
    try:
        ingestion = PrometeoIngestion(client)
        result = ingestion.sync_account(
            session_key=req.session_key,
            tenant_id=req.tenant_id,
            date_start=req.date_start,
            date_end=req.date_end,
        )
        return result
    finally:
        client.close()


@router.post("/sync/transfer-logs")
async def sync_transfer_logs(req: SyncRequest):
    """Sync transfer logs from Prometeo into the pipeline."""
    client = _get_client()
    try:
        ingestion = PrometeoIngestion(client)
        result = ingestion.sync_transfer_logs(
            tenant_id=req.tenant_id,
            date_start=req.date_start,
            date_end=req.date_end,
        )
        return result
    finally:
        client.close()


# ── Transfers: Enrollment ──


class EnrollRequest(BaseModel):
    session_key: str
    destination_institution: str
    destination_account: str
    destination_owner_name: str
    currency: str | None = None
    account_type: str | None = None
    document_number: str | None = None
    document_type: str | None = None
    authorization_data: str | None = None


class EnrollConfirmRequest(BaseModel):
    session_key: str
    request_id: str
    authorization_data: str


class EnrollRemoveRequest(BaseModel):
    session_key: str
    destination_account: str
    destination_institution: str | None = None
    authorization_data: str | None = None


@router.get("/transfers/enroll-form")
async def get_enroll_form(session_key: str = Query(...)):
    """Get required fields for pre-enrolling a destination account."""
    client = _get_client()
    try:
        return {"fields": client.get_enroll_form_fields(session_key)}
    finally:
        client.close()


@router.post("/transfers/enroll")
async def enroll_account(req: EnrollRequest):
    """Pre-enroll a destination account for transfers."""
    client = _get_client()
    try:
        return client.enroll_account(
            session_key=req.session_key,
            destination_institution=req.destination_institution,
            destination_account=req.destination_account,
            destination_owner_name=req.destination_owner_name,
            currency=req.currency,
            account_type=req.account_type,
            document_number=req.document_number,
            document_type=req.document_type,
            authorization_data=req.authorization_data,
        )
    finally:
        client.close()


@router.post("/transfers/enroll/confirm")
async def confirm_enrollment(req: EnrollConfirmRequest):
    """Confirm account enrollment when subsequent authorization is required."""
    client = _get_client()
    try:
        return client.confirm_enrollment(req.session_key, req.request_id, req.authorization_data)
    finally:
        client.close()


@router.post("/transfers/enroll/remove")
async def remove_enrollment(req: EnrollRemoveRequest):
    """Remove a pre-enrolled destination account."""
    client = _get_client()
    try:
        return client.remove_enrollment(
            req.session_key, req.destination_account,
            req.destination_institution, req.authorization_data,
        )
    finally:
        client.close()


# ── Transfers: Destinations & Form Fields ──


@router.get("/transfers/destinations")
async def get_destinations(session_key: str = Query(...)):
    """List institutions available as transfer destinations."""
    client = _get_client()
    try:
        return {"destinations": client.get_transfer_destinations(session_key)}
    finally:
        client.close()


@router.get("/transfers/form-fields")
async def get_form_fields(session_key: str = Query(...)):
    """Get required fields for making a transfer (varies by provider)."""
    client = _get_client()
    try:
        return {"fields": client.get_transfer_form_fields(session_key)}
    finally:
        client.close()


@router.get("/transfers/mfa-methods")
async def get_mfa_methods(session_key: str = Query(...)):
    """Get available MFA methods required to confirm transfers."""
    client = _get_client()
    try:
        return {"methods": client.get_transfer_mfa_methods(session_key)}
    finally:
        client.close()


# ── Transfers: Preprocess & Confirm ──


class TransferPreprocessRequest(BaseModel):
    session_key: str
    origin_account: str
    destination_institution: str
    destination_account: str
    currency: str
    amount: float
    concept: str
    destination_owner_name: str | None = None
    branch: str | None = None
    destination_account_type: str | None = None
    document_number: str | None = None
    document_type: str | None = None
    reason: str | None = None
    origin_holder: str | None = None
    origin_cuit: str | None = None
    origin_cvu: str | None = None
    destination_cuit: str | None = None


class TransferConfirmRequest(BaseModel):
    session_key: str
    request_id: str
    authorization_type: str | None = None
    authorization_data: str | None = None
    authorization_device_number: str | None = None


class TransferRetryRequest(BaseModel):
    session_key: str
    request_id: str


@router.post("/transfers/preprocess")
async def preprocess_transfer(req: TransferPreprocessRequest):
    """Preprocess a transfer. Returns request_id and authorization_devices for confirmation."""
    client = _get_client()
    try:
        return client.preprocess_transfer(
            session_key=req.session_key,
            origin_account=req.origin_account,
            destination_institution=req.destination_institution,
            destination_account=req.destination_account,
            currency=req.currency,
            amount=req.amount,
            concept=req.concept,
            destination_owner_name=req.destination_owner_name,
            branch=req.branch,
            destination_account_type=req.destination_account_type,
            document_number=req.document_number,
            document_type=req.document_type,
            reason=req.reason,
            origin_holder=req.origin_holder,
            origin_cuit=req.origin_cuit,
            origin_cvu=req.origin_cvu,
            destination_cuit=req.destination_cuit,
        )
    finally:
        client.close()


@router.post("/transfers/preprocess/retry")
async def retry_preprocess(req: TransferRetryRequest):
    """Retry a failed preprocess with the same data."""
    client = _get_client()
    try:
        return client.retry_preprocess_transfer(req.session_key, req.request_id)
    finally:
        client.close()


@router.post("/transfers/confirm")
async def confirm_transfer(req: TransferConfirmRequest):
    """Confirm a preprocessed transfer with optional MFA authorization."""
    client = _get_client()
    try:
        return client.confirm_transfer(
            session_key=req.session_key,
            request_id=req.request_id,
            authorization_type=req.authorization_type,
            authorization_data=req.authorization_data,
            authorization_device_number=req.authorization_device_number,
        )
    finally:
        client.close()


@router.post("/transfers/detail")
async def get_transfer_detail(session_key: str = Query(...), request_id: str = Query(...)):
    """Get details of a specific transfer."""
    client = _get_client()
    try:
        return client.get_transfer_detail(session_key, request_id)
    finally:
        client.close()


# ── Transfers: Logs ──


@router.get("/transfers/logs")
async def get_transfer_logs(
    date_start: str = Query(..., description="DD/MM/YYYY"),
    date_end: str = Query(..., description="DD/MM/YYYY"),
):
    """Get all transfer logs across providers."""
    client = _get_client()
    try:
        logs = client.get_transfer_logs(date_start, date_end)
        return {"transfers": [l.model_dump() for l in logs], "count": len(logs)}
    finally:
        client.close()


@router.get("/transfers/logs/{request_id}")
async def get_transfer_log_detail(request_id: str):
    """Get details for a specific transfer log entry."""
    client = _get_client()
    try:
        return client.get_transfer_log_detail(request_id)
    finally:
        client.close()


# ── Transfers: Validation ──


class ValidateAccountRequest(BaseModel):
    session_key: str
    account: str
    account_type: str | None = None
    bank_code: str | None = None


@router.post("/transfers/validate-account")
async def validate_account(req: ValidateAccountRequest):
    """Validate a destination account before transfer (BROU UY, BBVA, Interbank PE)."""
    client = _get_client()
    try:
        return client.validate_account(
            session_key=req.session_key,
            account=req.account,
            account_type=req.account_type,
            bank_code=req.bank_code,
        )
    finally:
        client.close()


# ── Transfers: Batch (Telecrédito BCP Perú) ──


class BatchPreprocessRequest(BaseModel):
    session_key: str
    data: str  # JSON or base64
    format: str = "json"


class BatchConfirmRequest(BaseModel):
    session_key: str
    request_id: str
    authorization_type: str | None = None
    authorization_data: str | None = None


class BatchDetailRequest(BaseModel):
    session_key: str
    request_id: str
    format: str = "csv"  # csv, xls, txt
    separator: str | None = None


@router.post("/transfers/batch/preprocess")
async def preprocess_batch(req: BatchPreprocessRequest):
    """Preprocess a batch of transfers."""
    client = _get_client()
    try:
        return client.preprocess_batch_transfer(req.session_key, req.data, req.format)
    finally:
        client.close()


@router.post("/transfers/batch/confirm")
async def confirm_batch(req: BatchConfirmRequest):
    """Confirm a batch transfer."""
    client = _get_client()
    try:
        return client.confirm_batch_transfer(
            req.session_key, req.request_id, req.authorization_type, req.authorization_data,
        )
    finally:
        client.close()


@router.post("/transfers/batch/detail")
async def get_batch_detail(req: BatchDetailRequest):
    """Get details of a batch transfer (csv/xls/txt)."""
    client = _get_client()
    try:
        return client.get_batch_transfer_detail(
            req.session_key, req.request_id, req.format, req.separator,
        )
    finally:
        client.close()


# ── Sync & Logout ──


@router.post("/logout")
async def logout(session_key: str = Query(...)):
    """Logout from Prometeo session."""
    client = _get_client()
    try:
        ok = client.logout(session_key)
        return {"logged_out": ok}
    finally:
        client.close()
