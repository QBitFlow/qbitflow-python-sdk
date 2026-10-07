"""A marketplace: invite a seller, then sell on their behalf, read their held funds, trust them.

QBITFLOW_API_KEY=sk_… SELLER_EMAIL=seller@example.com python examples/marketplace.py
QBITFLOW_API_KEY=sk_… MEMBER_UUID=… [TRUST=1] python examples/marketplace.py
"""

import os
import sys
import time

from _common import new_client

from qbitflow import ConflictError, QBitFlow


def invite(client: QBitFlow) -> None:
    email = os.environ.get("SELLER_EMAIL", "")
    if not email:
        sys.exit("set SELLER_EMAIL (to invite) or MEMBER_UUID (to act for a member)")
    try:
        created = client.invitations.create(
            email=email,
            trust_layer=True,  # hold their payments until members.trust
            organization_fee_percent=5.0,  # the organization keeps 5% of the seller's payments
            redirect_url="https://market.example.com/welcome",
        )
    except ConflictError as exc:
        if exc.code == "already_joined":
            print(email, "is already a member")
            return
        raise
    # The seller exists once they accept: wait for the member.joined webhook (its userUuid).
    print(f"invitation {created.invitation.uuid} sent; link: {created.link}")


def sell_as(client: QBitFlow, member_uuid: str) -> None:
    member = client.members.get(member_uuid)
    print(f"member {member.name} {member.last_name}, trusted: {member.trusted_at is not None}")

    if not client.wallets.list_supported_currencies(user_uuid=member_uuid):
        print("the seller has no wallet yet: their checkouts would answer 409 merchant_not_ready")
        return

    seller = client.on_behalf_of(member_uuid)  # every request acts in the seller's space
    product = seller.products.create(
        name="Handmade mug", price=4.5, reference=f"mug-{int(time.time())}"
    )  # 403 policy_disabled if members.products is off
    session = seller.checkout_sessions.create_payment(
        product_uuid=product.uuid, success_url="https://market.example.com/orders/{{UUID}}"
    )
    print("the buyer pays at", session.link)

    held = client.members.get_held_funds(member_uuid)
    print(f"held for them: {held.total_amount:.2f} USD over {len(held.ledgers)} lines")
    print(f"as seen by the seller: {seller.members.get_own_held_funds().total_amount:.2f} USD")

    if member.trusted_at is None and os.environ.get("TRUST") == "1":
        trusted = client.members.trust(member_uuid)
        print("trusted since", trusted.trusted_at)


def main() -> None:
    with new_client() as client:
        member_uuid = os.environ.get("MEMBER_UUID", "")
        if member_uuid:
            sell_as(client, member_uuid)
        else:
            invite(client)


if __name__ == "__main__":
    main()
