"""The same seller call one layer lower: a Protocol whose callbacks fill a Future."""

import asyncio

from sellers import Offer
from sellers_net import running_sellers


class SellerProtocol(asyncio.Protocol):
    def __init__(self, item, answer):
        self.item, self.answer, self.buffer = item, answer, b""

    def connection_made(self, transport):  # called by the loop once connected
        transport.write(f"{self.item}\n".encode())

    def data_received(self, data):  # called by the loop with whatever bytes arrived
        self.buffer += data

    def connection_lost(self, exc):  # the seller closed the connection
        if not self.answer.done():
            name, price = self.buffer.decode().split()
            self.answer.set_result(Offer(name, int(price)))


async def ask_seller(port, item):
    loop = asyncio.get_running_loop()
    answer = loop.create_future()
    transport, _ = await loop.create_connection(lambda: SellerProtocol(item, answer), "127.0.0.1", port)
    try:
        return await answer
    finally:
        transport.close()


async def main():
    with running_sellers() as ports:
        offer = await ask_seller(ports["seller-b"], "kettle-1l")
    print(f"protocol version: {offer.seller} offers {offer.price:,}")


asyncio.run(main())
