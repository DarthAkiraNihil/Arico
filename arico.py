from fractions import Fraction
from decimal import Decimal


class Arico:
    def __init__(self, data):
        self._data = data
        self._length = len(data)

    def encode(self):
        statistic = {b: 0 for b in range(0x000, 0x100)}
        for b in self._data:
            statistic[b] += 1
        
        significant = {
            k: Fraction(v, self._length) for k, v in statistic.items() if v > 0
        }
        significant_keys = list(significant.keys())

        distribution = dict()
        for idx, k in enumerate(significant_keys):
            if idx == 0:
                distribution[k] = (0, significant[k])
            else:
                distribution[k] = (
                    distribution[significant_keys[idx - 1]][1],
                    distribution[significant_keys[idx - 1]][1] + significant[k]
                )

        low, high = Fraction(0, 1), Fraction(1, 1)

        for byte in self._data:
            rng = high - low
            high = low + rng * distribution[byte][1]
            low = low + rng * distribution[byte][0]

        return low, distribution

    def decode(self, code, dist):
        
        code = Fraction(Decimal(code))

        decoded = list()

        for _ in range(self._length):
            for k, v in dist.items():
                if v[0] <= code < v[1]:
                    decoded.append(k)
                    rng = v[1] - v[0]
                    code = (code - v[0]) / rng
                    print(f"CODO: {code}")
                    break

        return decoded
if __name__ == '__main__':
    inp = [0xe0, 0xf0, 0xe8, 0xf4, 0xec, 0xe5, 0xf2, 0xe8, 0xea, 0xe0]
    arico = Arico(inp)
    res, dist = arico.encode()

    print(f"frac: {res}")
    print("dec: {0:f}".format(Decimal(res.numerator) / Decimal(res.denominator)))

    dec = arico.decode('{0:f}'.format(Decimal(res.numerator) / Decimal(res.denominator)), dist)
    print(f"decc: {dec}")

    flag = True

    for inx in range(len(inp)):
        if inp[inx] != dec[inx]:
            flag = False

    if flag:
        print("CORRECT!!!")
    else:
        print("FAILURE")



