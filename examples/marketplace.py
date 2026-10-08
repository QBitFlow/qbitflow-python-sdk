"""A marketplace (organization key): invite sellers, manage members, act in a member's space.

QBITFLOW_API_KEY=sk_… [INVITE=1] [INVITATION_UUID=…] python examples/marketplace.py
QBITFLOW_API_KEY=sk_… MEMBER_UUID=… [UPDATE_FEE=1] [TRUST=1] [REMOVE=1] \\
    python examples/marketplace.py

INVITE=1 invites seller@example.com; INVITATION_UUID revokes that invitation. MEMBER_UUID is a
member's user uuid (Member.user_uuid, also in the member.joined webhook).
"""

import os

from _common import new_client

import qbitflow


def invite(client: qbitflow.QBitFlow) -> None:
    # docs:start members-invite
    created = client.invitations.create(
        email="seller@example.com",
        trust_layer=True,  # hold their funds until you trust them
        organization_fee_percent=10,  # your commission on their payments
        redirect_url="https://shop.example.com/sellers/welcome",
    )
    # The seller exists once they accept: wait for the member.joined webhook.
    print("invitation", created.invitation.uuid, "link:", created.link)  # also emailed
    # docs:end members-invite


def list_invitations(client: qbitflow.QBitFlow) -> None:
    # docs:start invitations-list
    page = client.invitations.list(status=qbitflow.InvitationStatus.PENDING)
    for invitation in page.items:
        print(invitation.uuid, invitation.email, "expires", invitation.expires_at)
    # docs:end invitations-list


def revoke(client: qbitflow.QBitFlow, invitation_uuid: str) -> None:
    # docs:start invitations-revoke
    invitation = client.invitations.revoke(invitation_uuid)  # a pending one only
    print(invitation.status)  # revoked
    # docs:end invitations-revoke


def list_members(client: qbitflow.QBitFlow) -> None:
    # docs:start members-list
    page = client.members.list()
    for member in page.items:
        print(member.user_uuid, member.email, f"fee {member.organization_fee_percent}%")
    # docs:end members-list


def show_member(client: qbitflow.QBitFlow, member_uuid: str) -> None:
    # docs:start members-get
    member = client.members.get(member_uuid)  # their user uuid
    print(member.name, member.last_name, "trusted:", member.trusted_at is not None)
    # docs:end members-get


def member_wallets(client: qbitflow.QBitFlow, member_uuid: str) -> None:
    # docs:start members-wallets
    for wallet in client.wallets.list_for_member(member_uuid):
        print(wallet.currency.symbol, wallet.public_key)
    # docs:end members-wallets


def act_for_member(client: qbitflow.QBitFlow, member_uuid: str) -> qbitflow.QBitFlow:
    # docs:start client-on-behalf-of
    # Every request of this client sends On-Behalf-Of: it acts in the member's space.
    seller = client.on_behalf_of(member_uuid)  # shares the connections and settings of client
    products = seller.products.list()
    print(len(products), "products in the seller's space")
    # docs:end client-on-behalf-of
    return seller


def held_funds(client: qbitflow.QBitFlow, member_uuid: str) -> None:
    # docs:start members-held-funds
    for summary in client.members.list_held_funds():  # every member you hold funds for
        print(summary.user_uuid, f"{summary.total_amount:.2f} USD over {summary.count} lines")

    held = client.members.get_held_funds(member_uuid)  # one member, line by line
    print(f"owed to the seller: {held.total_amount:.2f} USD over {len(held.ledgers)} lines")
    # docs:end members-held-funds


def own_held_funds(client: qbitflow.QBitFlow) -> None:
    # docs:start members-own-held-funds
    # With a member's key, or a client acting on behalf of the member.
    held = client.members.get_own_held_funds()
    print(f"held for me: {held.total_amount:.2f} USD over {len(held.ledgers)} lines")
    # docs:end members-own-held-funds


def update_fee(client: qbitflow.QBitFlow, member_uuid: str) -> None:
    # docs:start members-update
    # The fee on their new payments (a checkout already created keeps its fee).
    member = client.members.update(member_uuid, organization_fee_percent=10)
    print(member.organization_fee_percent)
    # docs:end members-update


def trust(client: qbitflow.QBitFlow, member_uuid: str) -> None:
    # docs:start members-trust
    # Their new payments go to their own wallets from now on. What is held stays held until you
    # release it from the dashboard (heldFunds.released tells you).
    member = client.members.trust(member_uuid)
    print("trusted since", member.trusted_at)
    # docs:end members-trust


def remove(client: qbitflow.QBitFlow, member_uuid: str) -> None:
    # docs:start members-remove
    try:
        client.members.remove(member_uuid)  # their keys stop working, their checkouts close
        print("removed")
    except qbitflow.ConflictError as exc:
        if exc.code != "held_funds_pending":
            raise
        print("release their held funds first")  # from the dashboard
    # docs:end members-remove


def main() -> None:
    with new_client() as client:
        if os.environ.get("INVITE") == "1":
            try:
                invite(client)
            except qbitflow.ConflictError as exc:
                print("not invited:", exc.code)  # e.g. already_joined
        list_invitations(client)
        invitation_uuid = os.environ.get("INVITATION_UUID", "")
        if invitation_uuid:
            revoke(client, invitation_uuid)
        list_members(client)

        member_uuid = os.environ.get("MEMBER_UUID", "")
        if not member_uuid:
            print("set MEMBER_UUID to act for a member")
            return
        show_member(client, member_uuid)
        member_wallets(client, member_uuid)
        seller = act_for_member(client, member_uuid)
        held_funds(client, member_uuid)
        own_held_funds(seller)
        if os.environ.get("UPDATE_FEE") == "1":
            update_fee(client, member_uuid)
        if os.environ.get("TRUST") == "1":
            trust(client, member_uuid)
        if os.environ.get("REMOVE") == "1":
            remove(client, member_uuid)


if __name__ == "__main__":
    main()
