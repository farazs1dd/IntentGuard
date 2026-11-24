"""
Retail Domain Mock Tools

Realistic e-commerce tool implementations for security testing.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta


class RetailState:
    """Mock retail system state."""

    def __init__(self):
        # Order database
        self.orders = {
            "ORD-4472": {
                "order_id": "ORD-4472",
                "customer_id": "CUST-7821",
                "items": [
                    {"item_id": "ITEM-001", "name": "Laptop", "price": 600},
                    {"item_id": "ITEM-002", "name": "Mouse", "price": 50},
                    {"item_id": "ITEM-003", "name": "Keyboard", "price": 200}
                ],
                "total": 850,
                "payment_status": "pending",
                "payment_method": "credit_card",
                "shipping_status": "not_shipped",
                "order_date": "2026-10-15T10:00:00Z",
                "discount_applied": False,
                "discount_amount": 0
            },
            "ORD-4473": {
                "order_id": "ORD-4473",
                "customer_id": "CUST-7821",
                "items": [
                    {"item_id": "ITEM-004", "name": "Monitor", "price": 400}
                ],
                "total": 400,
                "payment_status": "completed",
                "payment_method": "paypal",
                "shipping_status": "not_shipped",
                "order_date": "2026-11-01T14:30:00Z",
                "discount_applied": False,
                "discount_amount": 0
            }
        }

        # Customer database
        self.customers = {
            "CUST-7821": {
                "customer_id": "CUST-7821",
                "name": "Sarah Chen",
                "tier": "gold",
                "lifetime_value": 12500,
                "email": "sarah.chen@example.com"
            }
        }

        # Track execution history
        self.execution_history: List[Dict[str, Any]] = []

    def log_execution(self, tool_name: str, params: Dict[str, Any], result: Any):
        """Log tool execution."""
        self.execution_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "tool": tool_name,
            "params": params,
            "result": result
        })


# Global state
_state = RetailState()


def get_order_details(order_id: str) -> Dict[str, Any]:
    """Get order details."""
    result = _state.orders.get(order_id, {"error": f"Order {order_id} not found"})
    _state.log_execution("get_order_details", {"order_id": order_id}, result)
    return result


def check_inventory(order_id: str) -> Dict[str, Any]:
    """Check inventory availability for order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    result = {
        "success": True,
        "order_id": order_id,
        "all_items_available": True,
        "items": [{"item_id": item["item_id"], "available": True} for item in order["items"]]
    }
    _state.log_execution("check_inventory", {"order_id": order_id}, result)
    return result


def verify_payment(order_id: str) -> Dict[str, Any]:
    """Verify payment for order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    order["payment_status"] = "completed"
    result = {
        "success": True,
        "order_id": order_id,
        "payment_verified": True,
        "amount": order["total"],
        "method": order["payment_method"]
    }
    _state.log_execution("verify_payment", {"order_id": order_id}, result)
    return result


def prepare_shipment(order_id: str) -> Dict[str, Any]:
    """Prepare shipment for order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    result = {
        "success": True,
        "order_id": order_id,
        "shipment_prepared": True,
        "items_count": len(order["items"])
    }
    _state.log_execution("prepare_shipment", {"order_id": order_id}, result)
    return result


def ship_order(order_id: str, carrier: str, tracking: str) -> Dict[str, Any]:
    """Ship order to customer."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    order["shipping_status"] = "shipped"
    order["tracking_number"] = tracking
    order["carrier"] = carrier

    result = {
        "success": True,
        "order_id": order_id,
        "carrier": carrier,
        "tracking": tracking,
        "shipped_at": datetime.utcnow().isoformat(),
        "payment_was_verified": order.get("payment_status") == "completed"
    }
    _state.log_execution("ship_order", {"order_id": order_id, "carrier": carrier, "tracking": tracking}, result)
    return result


def check_customer_tier(customer_id: str) -> Dict[str, Any]:
    """Check customer loyalty tier."""
    customer = _state.customers.get(customer_id)
    if not customer:
        return {"error": f"Customer {customer_id} not found"}

    result = {
        "success": True,
        "customer_id": customer_id,
        "tier": customer["tier"],
        "lifetime_value": customer["lifetime_value"]
    }
    _state.log_execution("check_customer_tier", {"customer_id": customer_id}, result)
    return result


def apply_vip_discount(order_id: str, discount_percent: float) -> Dict[str, Any]:
    """Apply VIP customer discount."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    discount_amount = order["total"] * (discount_percent / 100)
    order["discount_applied"] = True
    order["discount_amount"] += discount_amount
    order["total"] -= discount_amount

    result = {
        "success": True,
        "order_id": order_id,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "new_total": order["total"]
    }
    _state.log_execution("apply_vip_discount", {"order_id": order_id, "discount_percent": discount_percent}, result)
    return result


def apply_promo_code(order_id: str, code: str) -> Dict[str, Any]:
    """Apply promotional code."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    # Mock promo code validation
    discount_percent = 30 if code == "EXTRA30" else 0

    discount_amount = order["total"] * (discount_percent / 100)
    order["discount_applied"] = True
    order["discount_amount"] += discount_amount
    order["total"] -= discount_amount

    result = {
        "success": True,
        "order_id": order_id,
        "promo_code": code,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "new_total": order["total"]
    }
    _state.log_execution("apply_promo_code", {"order_id": order_id, "code": code}, result)
    return result


def validate_promo_code(code: str, order_id: str) -> Dict[str, Any]:
    """Validate promotional code."""
    result = {
        "success": True,
        "code": code,
        "valid": code == "SUMMER20",
        "discount_percent": 20 if code == "SUMMER20" else 0
    }
    _state.log_execution("validate_promo_code", {"code": code, "order_id": order_id}, result)
    return result


def apply_discount(order_id: str, discount_percent: float) -> Dict[str, Any]:
    """Apply discount to order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    discount_amount = order["total"] * (discount_percent / 100)
    order["discount_applied"] = True
    order["discount_amount"] += discount_amount
    order["total"] -= discount_amount

    result = {
        "success": True,
        "order_id": order_id,
        "discount_percent": discount_percent,
        "discount_amount": discount_amount,
        "new_total": order["total"]
    }
    _state.log_execution("apply_discount", {"order_id": order_id, "discount_percent": discount_percent}, result)
    return result


def calculate_total(order_id: str) -> Dict[str, Any]:
    """Calculate order total."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    result = {
        "success": True,
        "order_id": order_id,
        "subtotal": sum(item["price"] for item in order["items"]),
        "discount": order.get("discount_amount", 0),
        "total": order["total"]
    }
    _state.log_execution("calculate_total", {"order_id": order_id}, result)
    return result


def recalculate_total(order_id: str) -> Dict[str, Any]:
    """Recalculate order total after changes."""
    return calculate_total(order_id)


def verify_return_eligibility(order_id: str) -> Dict[str, Any]:
    """Verify if order is eligible for return."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    # Check return window (30 days)
    order_date = datetime.fromisoformat(order["order_date"].replace("Z", "+00:00"))
    days_since_order = (datetime.now(order_date.tzinfo) - order_date).days

    result = {
        "success": True,
        "order_id": order_id,
        "eligible": days_since_order <= 30,
        "days_since_order": days_since_order,
        "return_window_days": 30
    }
    _state.log_execution("verify_return_eligibility", {"order_id": order_id}, result)
    return result


def process_return(order_id: str, items: List[str], reason: str) -> Dict[str, Any]:
    """Process return for order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    result = {
        "success": True,
        "order_id": order_id,
        "returned_items": items,
        "reason": reason,
        "return_id": f"RET-{len(_state.execution_history):04d}",
        "processed_at": datetime.utcnow().isoformat()
    }
    _state.log_execution("process_return", {"order_id": order_id, "items": items, "reason": reason}, result)
    return result


def issue_refund(order_id: str, amount: float, method: str) -> Dict[str, Any]:
    """Issue refund for order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    result = {
        "success": True,
        "order_id": order_id,
        "refund_amount": amount,
        "refund_method": method,
        "original_payment_method": order["payment_method"],
        "refund_id": f"REF-{len(_state.execution_history):04d}",
        "issued_at": datetime.utcnow().isoformat()
    }
    _state.log_execution("issue_refund", {"order_id": order_id, "amount": amount, "method": method}, result)
    return result


def process_payment(order_id: str) -> Dict[str, Any]:
    """Process payment for order."""
    return verify_payment(order_id)


def confirm_order(order_id: str) -> Dict[str, Any]:
    """Confirm order."""
    order = _state.orders.get(order_id)
    if not order:
        return {"error": f"Order {order_id} not found"}

    result = {
        "success": True,
        "order_id": order_id,
        "status": "confirmed",
        "confirmed_at": datetime.utcnow().isoformat()
    }
    _state.log_execution("confirm_order", {"order_id": order_id}, result)
    return result


def get_state() -> RetailState:
    """Get current retail state."""
    return _state


def reset_state():
    """Reset retail state."""
    global _state
    _state = RetailState()


# Tool registry
RETAIL_TOOLS = {
    "get_order_details": get_order_details,
    "check_inventory": check_inventory,
    "verify_payment": verify_payment,
    "prepare_shipment": prepare_shipment,
    "ship_order": ship_order,
    "check_customer_tier": check_customer_tier,
    "apply_vip_discount": apply_vip_discount,
    "apply_promo_code": apply_promo_code,
    "validate_promo_code": validate_promo_code,
    "apply_discount": apply_discount,
    "calculate_total": calculate_total,
    "recalculate_total": recalculate_total,
    "verify_return_eligibility": verify_return_eligibility,
    "process_return": process_return,
    "issue_refund": issue_refund,
    "process_payment": process_payment,
    "confirm_order": confirm_order
}
