"""LangChain tools for the Executor agent — core banking write operations."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from langchain_core.tools import tool

from sentinel_swarm.graph.neo4j_client import Neo4jClient

logger = structlog.get_logger("tools.execution")


@tool
def block_account(account_id: str, reason: str, case_id: str) -> dict:
    """Block a bank account in the core banking system.

    This is a WRITE operation — only the Executor agent may call this.
    Returns: status, rollback_id for potential reversal.
    """
    rollback_id = f"RB-{uuid.uuid4().hex[:12]}"
    logger.info(
        "account_blocked",
        account_id=account_id,
        reason=reason,
        case_id=case_id,
        rollback_id=rollback_id,
    )
    # In production: call core banking API to freeze account
    return {
        "action": "BLOCK_ACCOUNT",
        "account_id": account_id,
        "status": "SUCCESS",
        "rollback_id": rollback_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


@tool
def cancel_transaction(tx_id: str, reason: str, case_id: str) -> dict:
    """Cancel or reverse a pending/completed transaction.

    Returns: status, rollback_id.
    """
    rollback_id = f"RB-{uuid.uuid4().hex[:12]}"
    logger.info(
        "transaction_cancelled",
        tx_id=tx_id,
        reason=reason,
        case_id=case_id,
        rollback_id=rollback_id,
    )
    return {
        "action": "CANCEL_TRANSACTION",
        "tx_id": tx_id,
        "status": "SUCCESS",
        "rollback_id": rollback_id,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat(),
    }


@tool
def generate_ros(
    case_id: str,
    country: str,
    subject_name: str,
    subject_document: str,
    operation_description: str,
    suspicion_grounds: str,
    action_taken: str,
) -> dict:
    """Generate a Reporte de Operación Sospechosa (ROS).

    Args:
        country: 'UY' for SENACLAFT format, 'AR' for UIF electronic format.
    """
    ros_id = f"ROS-{uuid.uuid4().hex[:12]}"
    destination = "UIAF_UY" if country.upper() == "UY" else "UIF_AR"

    ros = {
        "ros_id": ros_id,
        "destination": destination,
        "format": "SENACLAFT" if country.upper() == "UY" else "UIF_RES_30_2017",
        "generated_at": datetime.utcnow().isoformat(),
        "case_id": case_id,
        "subject": {
            "name": subject_name,
            "document": subject_document,
            "country": country.upper(),
        },
        "operation_description": operation_description,
        "suspicion_grounds": suspicion_grounds,
        "action_taken": action_taken,
        "status": "GENERATED",
    }

    logger.info("ros_generated", ros_id=ros_id, destination=destination, case_id=case_id)
    return ros


@tool
def submit_ros(ros_id: str, destination: str) -> dict:
    """Submit a ROS to the regulatory authority (UIAF or UIF).

    In production, this sends the ROS electronically to the regulator.
    """
    logger.info("ros_submitted", ros_id=ros_id, destination=destination)
    # In production: HTTPS POST to regulator's secure endpoint
    return {
        "ros_id": ros_id,
        "destination": destination,
        "status": "SUBMITTED",
        "confirmation_number": f"CONF-{uuid.uuid4().hex[:8]}",
        "submitted_at": datetime.utcnow().isoformat(),
    }


@tool
def notify_compliance(case_id: str, verdict: str, summary: str, urgency: str = "HIGH") -> dict:
    """Send internal notification to the compliance team.

    Args:
        urgency: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'.
    """
    notification_id = f"NOT-{uuid.uuid4().hex[:8]}"
    logger.info(
        "compliance_notified",
        case_id=case_id,
        verdict=verdict,
        urgency=urgency,
        notification_id=notification_id,
    )
    return {
        "notification_id": notification_id,
        "case_id": case_id,
        "channel": "compliance_team",
        "urgency": urgency,
        "status": "DELIVERED",
        "timestamp": datetime.utcnow().isoformat(),
    }


@tool
def update_graph_status(account_id: str, status: str, labels: list[str] | None = None) -> dict:
    """Update a node's status and labels in the Neo4j graph.

    Args:
        status: New status (e.g., 'BLOCKED_FRAUD', 'UNDER_INVESTIGATION').
        labels: Additional labels to add (e.g., ['BLOCKED_FRAUD', 'HIGH_RISK']).
    """
    try:
        client = Neo4jClient()
        client.update_node_status(account_id, status, labels)
        client.close()
        logger.info("graph_updated", account_id=account_id, status=status, labels=labels)
        return {
            "account_id": account_id,
            "status": status,
            "labels_added": labels or [],
            "result": "SUCCESS",
        }
    except Exception as e:
        logger.error("graph_update_failed", account_id=account_id, error=str(e))
        return {"account_id": account_id, "result": "FAILED", "error": str(e)}


@tool
def notify_client(account_id: str, notification_type: str = "generic_security") -> dict:
    """Send a generic security notification to the client (anti-tipping-off compliant).

    The notification must NOT reveal the reason for any restrictions.
    """
    # Anti-tipping-off: generic message only
    messages = {
        "generic_security": (
            "Por motivos de seguridad, su cuenta ha sido temporalmente restringida. "
            "Por favor, comuníquese con su sucursal o llame a nuestra línea de atención "
            "al cliente para más información."
        ),
        "verification_required": (
            "Para su seguridad, necesitamos verificar información de su cuenta. "
            "Por favor, acérquese a su sucursal más cercana con su documento de identidad."
        ),
    }

    message = messages.get(notification_type, messages["generic_security"])
    notification_id = f"CLI-{uuid.uuid4().hex[:8]}"

    logger.info("client_notified", account_id=account_id, notification_id=notification_id)
    return {
        "notification_id": notification_id,
        "account_id": account_id,
        "message": message,
        "channel": "sms_and_push",
        "status": "SENT",
        "anti_tipping_off_compliant": True,
        "timestamp": datetime.utcnow().isoformat(),
    }
