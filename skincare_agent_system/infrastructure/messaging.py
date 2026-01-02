"""
Agent Messaging: Request/Response messaging with acknowledgment protocol.
Enables direct agent-to-agent communication with reliability guarantees.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger("AgentMessaging")


class MessageType(Enum):
    """Types of agent messages."""
    REQUEST = "request"  # Expects response
    RESPONSE = "response"  # Reply to request
    NOTIFICATION = "notification"  # Fire-and-forget
    ACK = "ack"  # Acknowledgment
    NACK = "nack"  # Negative acknowledgment
    BID = "bid"  # Negotiation bid
    ACCEPT = "accept"  # Accept bid
    REJECT = "reject"  # Reject bid


class MessagePriority(Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class DeliveryStatus(Enum):
    """Message delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Message:
    """
    Agent-to-agent message with delivery tracking.
    """
    message_id: str
    message_type: MessageType
    sender: str
    receiver: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    correlation_id: Optional[str] = None  # Links request/response
    reply_to: Optional[str] = None  # For responses
    ttl_seconds: float = 30.0  # Time to live
    requires_ack: bool = True
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    retries: int = 0

    def is_expired(self) -> bool:
        """Check if message has expired."""
        created = datetime.fromisoformat(self.timestamp)
        expiry = created + timedelta(seconds=self.ttl_seconds)
        return datetime.now() > expiry

    def create_response(
        self,
        payload: Dict[str, Any],
        success: bool = True
    ) -> "Message":
        """Create a response to this message."""
        return Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.RESPONSE,
            sender=self.receiver,
            receiver=self.sender,
            payload=payload,
            correlation_id=self.message_id,
            reply_to=self.message_id,
            requires_ack=False
        )

    def create_ack(self) -> "Message":
        """Create acknowledgment for this message."""
        return Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.ACK,
            sender=self.receiver,
            receiver=self.sender,
            payload={"acknowledged": self.message_id},
            correlation_id=self.message_id,
            requires_ack=False,
            ttl_seconds=10.0
        )

    def create_nack(self, reason: str) -> "Message":
        """Create negative acknowledgment."""
        return Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.NACK,
            sender=self.receiver,
            receiver=self.sender,
            payload={"message_id": self.message_id, "reason": reason},
            correlation_id=self.message_id,
            requires_ack=False,
            ttl_seconds=10.0
        )


@dataclass
class DeadLetter:
    """Record of failed message delivery."""
    message: Message
    failure_reason: str
    failure_time: str
    retry_count: int


class MessageRouter:
    """
    Routes messages between agents.
    Handles delivery, acknowledgment, and retries.
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
        ack_timeout_seconds: float = 5.0
    ):
        self._handlers: Dict[str, Callable[[Message], Optional[Message]]] = {}
        self._pending_acks: Dict[str, Message] = {}  # message_id -> message
        self._dead_letters: List[DeadLetter] = []
        self._message_history: List[Message] = []
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._ack_timeout = ack_timeout_seconds
        self._max_dead_letters = 100

    def register_handler(
        self,
        agent_name: str,
        handler: Callable[[Message], Optional[Message]]
    ) -> None:
        """Register a message handler for an agent."""
        self._handlers[agent_name] = handler
        logger.debug(f"Registered handler for {agent_name}")

    def unregister_handler(self, agent_name: str) -> None:
        """Unregister an agent's handler."""
        self._handlers.pop(agent_name, None)

    async def send(self, message: Message) -> Optional[Message]:
        """
        Send a message and wait for response if applicable.

        Returns:
            Response message for REQUEST type, None otherwise
        """
        message.delivery_status = DeliveryStatus.SENT
        self._message_history.append(message)

        # Check if receiver exists
        handler = self._handlers.get(message.receiver)
        if not handler:
            message.delivery_status = DeliveryStatus.FAILED
            self._add_dead_letter(message, "No handler registered")
            return None

        # Deliver message
        try:
            message.delivery_status = DeliveryStatus.DELIVERED
            response = handler(message)

            # Track for ACK if required
            if message.requires_ack:
                self._pending_acks[message.message_id] = message

            # Wait for ACK if required
            if message.requires_ack:
                ack_received = await self._wait_for_ack(message.message_id)
                if ack_received:
                    message.delivery_status = DeliveryStatus.ACKNOWLEDGED
                else:
                    # Retry logic
                    while message.retries < self._max_retries:
                        message.retries += 1
                        await asyncio.sleep(self._retry_delay)
                        response = handler(message)
                        if await self._wait_for_ack(message.message_id):
                            message.delivery_status = DeliveryStatus.ACKNOWLEDGED
                            break
                    else:
                        message.delivery_status = DeliveryStatus.FAILED
                        self._add_dead_letter(message, "ACK timeout after retries")

            return response

        except Exception as e:
            message.delivery_status = DeliveryStatus.FAILED
            self._add_dead_letter(message, str(e))
            logger.error(f"Message delivery failed: {e}")
            return None

    def send_sync(self, message: Message) -> Optional[Message]:
        """Synchronous send (for non-async contexts)."""
        message.delivery_status = DeliveryStatus.SENT
        self._message_history.append(message)

        handler = self._handlers.get(message.receiver)
        if not handler:
            message.delivery_status = DeliveryStatus.FAILED
            self._add_dead_letter(message, "No handler registered")
            return None

        try:
            message.delivery_status = DeliveryStatus.DELIVERED
            return handler(message)
        except Exception as e:
            message.delivery_status = DeliveryStatus.FAILED
            self._add_dead_letter(message, str(e))
            return None

    async def _wait_for_ack(self, message_id: str) -> bool:
        """Wait for acknowledgment with timeout."""
        start = datetime.now()
        while (datetime.now() - start).total_seconds() < self._ack_timeout:
            if message_id not in self._pending_acks:
                return True  # ACK received
            await asyncio.sleep(0.1)
        return False

    def acknowledge(self, message_id: str) -> None:
        """Mark message as acknowledged."""
        self._pending_acks.pop(message_id, None)
        logger.debug(f"Message {message_id} acknowledged")

    def _add_dead_letter(self, message: Message, reason: str) -> None:
        """Add message to dead letter queue."""
        dead = DeadLetter(
            message=message,
            failure_reason=reason,
            failure_time=datetime.now().isoformat(),
            retry_count=message.retries
        )
        self._dead_letters.append(dead)

        # Prune if too many
        if len(self._dead_letters) > self._max_dead_letters:
            self._dead_letters = self._dead_letters[-self._max_dead_letters:]

        logger.warning(f"Dead letter: {message.message_id} - {reason}")

    def get_dead_letters(self) -> List[DeadLetter]:
        """Get dead letter queue."""
        return self._dead_letters.copy()

    def get_pending_acks(self) -> List[Message]:
        """Get messages waiting for ACK."""
        return list(self._pending_acks.values())

    def get_message_history(self, limit: int = 50) -> List[Message]:
        """Get recent message history."""
        return self._message_history[-limit:]

    def clear_expired(self) -> int:
        """Clear expired messages from tracking."""
        expired = [
            mid for mid, msg in self._pending_acks.items()
            if msg.is_expired()
        ]
        for mid in expired:
            msg = self._pending_acks.pop(mid)
            self._add_dead_letter(msg, "Expired")
        return len(expired)


class AgentMessenger:
    """
    High-level messaging interface for agents.
    """

    def __init__(self, agent_name: str, router: MessageRouter):
        self._agent_name = agent_name
        self._router = router
        self._response_handlers: Dict[str, asyncio.Event] = {}
        self._responses: Dict[str, Message] = {}

    async def ask(
        self,
        receiver: str,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0
    ) -> Optional[Dict[str, Any]]:
        """
        Send a request and wait for response.
        """
        message = Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.REQUEST,
            sender=self._agent_name,
            receiver=receiver,
            payload={"question": question, "context": context or {}},
            priority=MessagePriority.NORMAL,
            ttl_seconds=timeout
        )

        response = await self._router.send(message)

        if response and response.message_type == MessageType.RESPONSE:
            return response.payload

        return None

    def tell(
        self,
        receiver: str,
        notification: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a notification (fire-and-forget).
        """
        message = Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.NOTIFICATION,
            sender=self._agent_name,
            receiver=receiver,
            payload={"notification": notification, "data": data or {}},
            requires_ack=False
        )

        self._router.send_sync(message)
        return True

    async def bid(
        self,
        receiver: str,
        task: str,
        offer: Dict[str, Any],
        timeout: float = 5.0
    ) -> Optional[str]:
        """
        Send a bid in negotiation.
        Returns: 'accepted', 'rejected', or None if timeout
        """
        message = Message(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.BID,
            sender=self._agent_name,
            receiver=receiver,
            payload={"task": task, "offer": offer},
            ttl_seconds=timeout
        )

        response = await self._router.send(message)

        if response:
            if response.message_type == MessageType.ACCEPT:
                return "accepted"
            elif response.message_type == MessageType.REJECT:
                return "rejected"

        return None


# Factory functions
def create_message(
    sender: str,
    receiver: str,
    payload: Dict[str, Any],
    message_type: MessageType = MessageType.REQUEST,
    priority: MessagePriority = MessagePriority.NORMAL
) -> Message:
    """Create a new message."""
    return Message(
        message_id=str(uuid.uuid4()),
        message_type=message_type,
        sender=sender,
        receiver=receiver,
        payload=payload,
        priority=priority
    )


# Singleton router
_message_router: Optional[MessageRouter] = None


def get_message_router() -> MessageRouter:
    """Get or create message router singleton."""
    global _message_router
    if _message_router is None:
        _message_router = MessageRouter()
    return _message_router


def reset_message_router() -> None:
    """Reset message router (for testing)."""
    global _message_router
    _message_router = None
