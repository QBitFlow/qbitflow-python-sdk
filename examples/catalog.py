"""The catalog: create a product, list products and customers, sell a product by its reference.

QBITFLOW_API_KEY=sk_… python examples/catalog.py
"""

from _common import new_client

import qbitflow


def create_product(client: qbitflow.QBitFlow) -> qbitflow.Product:
    # docs:start products-create
    product = client.products.create(
        name="T-shirt",
        description="Blue, size M",
        price=4.99,  # USD
        reference="tshirt-blue-m",  # your own id: unique per space
    )
    print(product.uuid, product.payment_link)
    # docs:end products-create
    return product


def list_products(client: qbitflow.QBitFlow) -> None:
    # docs:start products-list
    for product in client.products.list():
        print(product.reference, product.name, product.price)
    # docs:end products-list


def list_customers(client: qbitflow.QBitFlow) -> None:
    # docs:start customers-list
    page = client.customers.list(limit=20)
    for customer in page.items:
        print(customer.uuid, customer.email, customer.reference)
    if page.has_more:
        print("next page: cursor =", page.next_cursor)  # pass it back as cursor=
    # docs:end customers-list


def sell_product(client: qbitflow.QBitFlow) -> qbitflow.CheckoutSession:
    # docs:start checkout-create-payment-product
    session = client.checkout_sessions.create_payment(
        product_reference="tshirt-blue-m",  # or product_uuid=
        reference="order-1042",
        success_url=f"https://shop.example.com/orders/success?uuid={qbitflow.PLACEHOLDER_UUID}",
        cancel_url="https://shop.example.com/orders/cancel",
    )
    print("Send the customer to", session.link)
    # docs:end checkout-create-payment-product
    return session


def main() -> None:
    with new_client() as client:
        try:
            create_product(client)
        except qbitflow.ConflictError as exc:
            if exc.code != "unique_violation":
                raise
            print("tshirt-blue-m exists:", client.products.get_by_reference("tshirt-blue-m").uuid)
        list_products(client)
        list_customers(client)
        session = sell_product(client)
        # This demo ends the checkout at once, which frees order-1042 for the next run.
        client.checkout_sessions.expire(session.uuid)


if __name__ == "__main__":
    main()
