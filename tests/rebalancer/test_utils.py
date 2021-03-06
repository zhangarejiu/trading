import unittest
from rebalancer.utils import get_mid_prices_from_orderbooks
from rebalancer.utils import get_weights_from_resources
from rebalancer.utils import dfs, topological_sort, bfs, parse_order
from rebalancer.utils import get_price_estimates_from_orderbooks
from rebalancer.utils import spread_to_fee, get_total_fee
from rebalancer.utils import rebalance_orders
from rebalancer.utils import get_portfolio_value_from_resources
from internals.orderbook import OrderBook
from internals.order import Order
from internals.enums import OrderType, OrderAction
from decimal import Decimal
from collections import defaultdict
import numpy as np


class UtilsTester(unittest.TestCase):
    def test_rebalance_orders(self):
        initial_weights = {'BTC': Decimal('0.2'),
                           'ETH': Decimal('0.3'),
                           'USDT': Decimal('0.5')}
        final_weights = {'BTC': Decimal('0.5'),
                         'ETH': Decimal('0.2'),
                         'USDT': Decimal('0.3')}

        fees = {'BTC_USDT': 1 - Decimal('0.002'), 'BTC_ETH': 1 - Decimal(
            '0.0018'), 'ETH_USDT': 1 - Decimal('0.0019')}

        orders = rebalance_orders(initial_weights, final_weights, fees)
        orders = [order for order in orders if order[2] > Decimal('1e-9')]
        orders.sort()
        self.assertEqual(orders[0], ('ETH', 'BTC', Decimal('0.1')))
        self.assertEqual(orders[1], ('USDT', 'BTC', Decimal('0.2')))

        fees = {'BTC_USDT': 1 - Decimal('0.002'), 'BTC_ETH': 1 - Decimal(
            '0.0008'), 'ETH_USDT': 1 - Decimal('0.0009')}

        orders = rebalance_orders(initial_weights, final_weights, fees)
        orders = [order for order in orders if order[2] > Decimal('1e-9')]
        orders.sort()
        self.assertEqual(orders[0], ('ETH', 'BTC', Decimal('0.3')))
        self.assertEqual(orders[1], ('USDT', 'ETH', Decimal('0.2')))

    def test_get_mid_prices_from_orderbooks(self):
        orderbook_BTC_USDT = OrderBook(
            'BTC_USDT', [Decimal('15000'), Decimal('5000')])

        orderbook_ETH_BTC = OrderBook(
            'ETH_BTC', [Decimal('0.005'), Decimal('0.003')])

        orderbook_ADA_BTC = OrderBook(
            'ADA_BTC', [Decimal('0.00003'), Decimal('0.00001')])

        orderbook_EOS_ETH = OrderBook(
            'EOS_ETH', [Decimal('0.03'), Decimal('0.01')])

        orderbooks = [orderbook_EOS_ETH, orderbook_ADA_BTC,
                      orderbook_ETH_BTC, orderbook_BTC_USDT]

        prices = get_mid_prices_from_orderbooks(orderbooks)
        correct_prices = {
            'BTC_USDT': Decimal('10000'),
            'ETH_BTC': Decimal('0.004'),
            'ADA_BTC': Decimal('0.00002'),
            'EOS_ETH': Decimal('0.02'),
            'USDT_BTC': Decimal('0.0001'),
            'BTC_ETH': Decimal('250'),
            'BTC_ADA': Decimal('50000'),
            'ETH_EOS': Decimal('50')
        }
        self.assertDictEqual(prices, correct_prices)

    def test_get_weights_from_resources(self):
        resources = {
            'BTC': Decimal('1'),
            'USDT': Decimal('1000'),
            'ETH': Decimal('10'),
            'LTC': Decimal('50')
        }
        prices = {
            'BTC': Decimal('10000'),
            'USDT': Decimal('1'),
            'ETH': Decimal('1000'),
            'LTC': Decimal('80')
        }
        correct_weights = {
            'BTC': Decimal('0.4'),
            'USDT': Decimal('0.04'),
            'ETH': Decimal('0.4'),
            'LTC': Decimal('0.16')
        }
        weights = get_weights_from_resources(resources, prices)
        self.assertDictEqual(weights, correct_weights)

    def test_get_portfolio_value_from_resources(self):
        resources = {
            'BTC': Decimal('1'),
            'USDT': Decimal('1000'),
            'ETH': Decimal('10'),
            'LTC': Decimal('50')
        }
        prices = {
            'BTC': Decimal('10000'),
            'USDT': Decimal('1'),
            'ETH': Decimal('1000'),
            'LTC': Decimal('80')
        }
        correct_portfolio_value = Decimal('25000')
        portfolio_value = get_portfolio_value_from_resources(resources, prices)
        self.assertEqual(portfolio_value, correct_portfolio_value)

    def test_topological_sort(self):
        orders = [('BTC', 'USDT', Decimal(1)),
                  ('USDT', 'ETH', Decimal(2)),
                  ('BTC', 'ADA', Decimal(3)),
                  ('ADA', 'ETH', Decimal(4)),
                  ('ETH', 'EOS', Decimal(5)),
                  ('USDT', 'LTC', Decimal(6)),
                  ('BNB', 'USDT', Decimal(7))]

        #                  BTC                   BNB
        #                  / \                   /
        #                 /   \                 /
        #                /     \               /
        #            3  /       \   1         / 7
        #              /         \           /
        #             /           \         /
        #            /             \       /
        #           /               \     /
        #          /                 \   /
        #         ADA                 USDT
        #           \                 / \
        #            \               /   \
        #             \             /     \
        #              \           /       \
        #            4  \         / 2       \   6
        #                \       /           \
        #                 \     /             \
        #                  \   /               \
        #                   ETH                LTC
        #                    |
        #                    |
        #                    | 5
        #                    |
        #                    |
        #                   EOS

        sorted_orders = topological_sort(orders)
        product_quantity = {'_'.join(order[:2]): order[2]
                            for order in sorted_orders}
        sorted_products = ['_'.join(order[:2]) for order in sorted_orders]

        for order in orders:
            self.assertEqual(product_quantity['_'.join(order[:2])], order[2])

        self.assertLess(sorted_products.index('BTC_USDT'),
                        sorted_products.index('USDT_LTC'))
        self.assertLess(sorted_products.index('BTC_USDT'),
                        sorted_products.index('USDT_ETH'))
        self.assertLess(sorted_products.index('BTC_USDT'),
                        sorted_products.index('ETH_EOS'))

        self.assertLess(sorted_products.index('BTC_ADA'),
                        sorted_products.index('ADA_ETH'))
        self.assertLess(sorted_products.index('BTC_ADA'),
                        sorted_products.index('ETH_EOS'))

        self.assertLess(sorted_products.index('BNB_USDT'),
                        sorted_products.index('USDT_ETH'))
        self.assertLess(sorted_products.index('BNB_USDT'),
                        sorted_products.index('USDT_LTC'))
        self.assertLess(sorted_products.index('BNB_USDT'),
                        sorted_products.index('ETH_EOS'))

        self.assertLess(sorted_products.index('ADA_ETH'),
                        sorted_products.index('ETH_EOS'))

        self.assertLess(sorted_products.index('USDT_ETH'),
                        sorted_products.index('ETH_EOS'))

    def test_dfs(self):
        graph = defaultdict(set, {
            'start': {'A', 'D'},
            'A': {'B', 'C'},
            'C': {'E', 'F'},
            'D': {'B', 'E'}})

        #                          start
        #                          /   \
        #                         /     \
        #                        /       \
        #                       A         D
        #                      / \       /|
        #                     /   \     / |
        #                    /     \   /  |
        #                   /       \ /   |
        #                  C         B    |
        #                 / \             /
        #                /   \           /
        #               /     \         /
        #              /       \       /
        #             /         \     /
        #            /           \   /
        #           F             \ /
        #                          E

        vertices = dfs(graph, set(), 'start')[::-1]

        for v1 in graph:
            for v2 in graph[v1]:
                self.assertLess(vertices.index(v1), vertices.index(v2))

        vertices = dfs(graph, set(), 'C')[::-1]
        self.assertEqual(len(vertices), 3)
        self.assertEqual(vertices[0], 'C')
        self.assertSetEqual(set(vertices), set('CEF'))

    def test_bfs(self):
        graph = defaultdict(dict, {
            'USDT': {'BTC': np.log(10000),
                     'ETH': np.log(1000),
                     'LTC': np.log(100),
                     'BNB': np.log(10)},
            'BTC': {'USDT': -np.log(10000),
                    'ETH': -np.log(11),
                    'LTC': -np.log(101)},
            'ETH': {'EOS': -np.log(10), 'LTC': -np.log(10)},
            'LTC': {'ETH': np.log(10)}
        })
        dists = bfs(graph, 'USDT')
        correct_dists = {
            'USDT': np.log(1),
            'BNB': np.log(10),
            'BTC': np.log(10000),
            'ETH': np.log(10000) - np.log(11),
            'LTC': np.log(1000) - np.log(11),
            'EOS': np.log(1000) - np.log(11)
        }
        self.assertDictAlmostEqual(dists, correct_dists)

        graph = defaultdict(dict, {
            'USDT': {'BTC': np.log(10000),
                     'ETH': np.log(1000),
                     'BNB': np.log(10)},
            'BTC': {'USDT': -np.log(10000),
                    'ETH': -np.log(11),
                    'LTC': -np.log(110)},
            'ETH': {'EOS': -np.log(10), 'LTC': -np.log(10)},
            'LTC': {'ETH': np.log(10)}
        })
        dists = bfs(graph, 'USDT')
        correct_dists = {
            'USDT': np.log(1),
            'BNB': np.log(10),
            'BTC': np.log(10000),
            'ETH': np.log(10000) - np.log(11),
            'LTC': np.log(1000) - np.log(11),
            'EOS': np.log(1000) - np.log(11)
        }
        self.assertDictAlmostEqual(dists, correct_dists)

    def test_get_price_estimates_from_orderbooks(self):

        orderbook_BTC_USDT = OrderBook('BTC_USDT', Decimal('10000'))
        orderbook_ETH_USDT = OrderBook('ETH_USDT', Decimal('1000'))
        orderbook_LTC_USDT = OrderBook('LTC_USDT', Decimal('100'))
        orderbook_BNB_USDT = OrderBook('BNB_USDT', Decimal('10'))
        orderbook_ETH_BTC = OrderBook('ETH_BTC', 1 / Decimal('11'))
        orderbook_LTC_BTC = OrderBook('LTC_BTC', 1 / Decimal('101'))
        orderbook_EOS_ETH = OrderBook('EOS_ETH', Decimal('0.1'))
        orderbook_LTC_ETH = OrderBook('LTC_ETH', Decimal('0.1'))

        orderbooks = [orderbook_BTC_USDT, orderbook_ETH_USDT,
                      orderbook_LTC_USDT, orderbook_BNB_USDT,
                      orderbook_ETH_BTC, orderbook_LTC_BTC,
                      orderbook_EOS_ETH, orderbook_LTC_ETH]

        price_estimates = get_price_estimates_from_orderbooks(
            orderbooks, 'USDT')

        correct_price_estimates = {
            'USDT': Decimal('1'),
            'BNB': Decimal('10'),
            'BTC': Decimal('10000'),
            'ETH': Decimal('10000') / Decimal('11'),
            'LTC': Decimal('1000') / Decimal('11'),
            'EOS': Decimal('1000') / Decimal('11')
        }
        self.assertDictAlmostEqual(correct_price_estimates, price_estimates)

    def test_spread_to_fee(self):
        fee = Decimal('0.001')
        orderbook = OrderBook(
            'BTC_USDT',
            [Decimal('1000') * (1 - fee), Decimal('1000') / (1 - fee)])
        self.assertEqual(spread_to_fee(orderbook), fee)

    def test_get_total_fee(self):
        fee = Decimal('0.001')
        spread_fee = Decimal('0.0015')
        price = Decimal('1000')
        wall_ask = price / (1 - spread_fee)
        wall_bid = price * (1 - spread_fee)
        orderbook = OrderBook('BTC_USDT', [wall_ask, wall_bid])
        correct_fee = 1 - (1 - spread_fee) * (1 - fee)
        self.assertAlmostEqual(get_total_fee(
            spread_to_fee(orderbook), fee), correct_fee, places=18)

    def test_parse_order(self):
        products = ['BTC_USDT', 'ETH_USDT', 'LTC_USDT',
                    'BNB_USDT', 'ETH_BTC', 'LTC_BTC', 'EOS_ETH', 'LTC_ETH']
        price_estimates = {
            'USDT': Decimal('1'),
            'BNB': Decimal('10'),
            'BTC': Decimal('10000'),
            'ETH': Decimal('10000') / Decimal('11'),
            'LTC': Decimal('1000') / Decimal('11'),
            'EOS': Decimal('1000') / Decimal('11')
        }
        pre_order = ('BTC', 'USDT', Decimal('10000'))
        order = parse_order(
            pre_order, products, price_estimates, 'USDT')
        correct_order = Order('BTC_USDT', OrderType.MARKET,
                              OrderAction.SELL, Decimal('1'))

        self.assertEqual(order.product, correct_order.product)
        self.assertEqual(order._action, correct_order._action)
        self.assertEqual(order._type, correct_order._type)
        self.assertEqual(order._quantity, correct_order._quantity)

        pre_order = ('USDT', 'BTC', Decimal('10000'))
        order = parse_order(
            pre_order, products, price_estimates, 'USDT')
        correct_order = Order('BTC_USDT', OrderType.MARKET,
                              OrderAction.BUY, Decimal('1'))

        self.assertEqual(order.product, correct_order.product)
        self.assertEqual(order._action, correct_order._action)
        self.assertEqual(order._type, correct_order._type)
        self.assertEqual(order._quantity, correct_order._quantity)

        pre_order = ('BNB', 'BTC', Decimal('10000'))
        order = parse_order(
            pre_order, products + ['BNB_BTC'], price_estimates, 'USDT')
        correct_order = Order('BNB_BTC', OrderType.MARKET,
                              OrderAction.SELL, Decimal('1000'))

        self.assertEqual(order.product, correct_order.product)
        self.assertEqual(order._action, correct_order._action)
        self.assertEqual(order._type, correct_order._type)
        self.assertEqual(order._quantity, correct_order._quantity)

        pre_order = ('ETH', 'EOS', Decimal('10000'))
        order = parse_order(
            pre_order, products, price_estimates, 'USDT')
        correct_order = Order('EOS_ETH', OrderType.MARKET,
                              OrderAction.BUY, Decimal('110'))

        self.assertEqual(order.product, correct_order.product)
        self.assertEqual(order._action, correct_order._action)
        self.assertEqual(order._type, correct_order._type)
        self.assertEqual(order._quantity, correct_order._quantity)

        pre_order = ('ETH', 'EOS', Decimal('10000'))
        order = parse_order(
            pre_order, products, price_estimates, 'USDT',
            OrderType.LIMIT, Decimal('1000'))

        correct_order = Order('EOS_ETH', OrderType.LIMIT,
                              OrderAction.BUY, Decimal('110'),
                              Decimal('1000'))

        self.assertEqual(order.product, correct_order.product)
        self.assertEqual(order._action, correct_order._action)
        self.assertEqual(order._type, correct_order._type)
        self.assertEqual(order._quantity, correct_order._quantity)
        self.assertEqual(order._price, correct_order._price)

        with self.assertRaises(AssertionError):
            parse_order(pre_order, products, price_estimates, 'USDT',
                        OrderType.LIMIT)

        with self.assertRaises(AssertionError):
            parse_order(pre_order, products, price_estimates, 'USDT',
                        OrderType.MARKET, Decimal('1000'))

    def assertDictAlmostEqual(self, d1, d2, *args, **kwargs):
        self.assertEqual(set(d1.keys()), set(d2.keys()))
        for i in d1:
            self.assertAlmostEqual(d1[i], d2[i], *args, **kwargs)
