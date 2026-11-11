
# Sample order data for demonstration only.
# These are not real customer orders.

SAMPLE_ORDERS = {
    "ORD1001": {
        "status": "Shipped",
        "estimated_delivery": "2026-10-25"
    },
    "ORD1002": {
        "status": "Processing",
        "estimated_delivery": "2026-10-27"
    },
    "ORD1003": {
        "status": "Delivered",
        "estimated_delivery": "2026-10-20"
    }
}


def get_order_status(order_id: str) -> dict:
    """Look up an order in the sample order database."""

    order_id = order_id.strip().upper()

    if not order_id:
        return {
            "found": False,
            "message": "Please provide an order ID."
        }

    order = SAMPLE_ORDERS.get(order_id)

    if order is None:
        return {
            "found": False,
            "message": (
                "Order not found in the sample database. "
                "Please check the order ID."
            )
        }

    return {
        "found": True,
        "order_id": order_id,
        "status": order["status"],
        "estimated_delivery": order["estimated_delivery"]
    }
