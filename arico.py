import sys
from fractions import Fraction
from decimal import Decimal
from typing import List


class Arico:
    def __init__(self, file):
        self._file = file
        self._data: List[int] = list()
        self._length = 0

    @staticmethod
    def _int_to_bytes(value: int, desired_length: int = None):

        transformed = [value % 256]
        value >>= 8

        while value != 0:
            transformed.append(value % 256)
            value >>= 8

        if desired_length is not None:
            while len(transformed) < desired_length:
                transformed.append(0)

        return transformed[::-1]


    def _pack(self, encode_result, counts):
        signature = [0x41, 0x52, 0x49]  # ARI

        length_of_length = (self._length.bit_length() + 7) // 8
        length_of_table = len(counts.keys())
        print(f"LOT: {length_of_table}")

        length = list(self._int_to_bytes(self._length))
        length_checkpoint = 0x2e

        counts_bytes = list()
        for k, v in counts.items():
            counts_bytes += [k, *self._int_to_bytes(v, length_of_length)]

        counts_checkpoint = 0x2e

        decimal_result = "{0:f}".format(Decimal(encode_result.numerator) / Decimal(encode_result.denominator))
        _solid, _partial = decimal_result.split('.')[0], decimal_result.split('.')[1]

        if int(_solid) == 0:
            encoded = [0x00]
        else:
            encoded = [0xff]

        encoded += self._int_to_bytes(int(_partial))

        return [*signature, length_of_length, length_of_table, *length, length_checkpoint, *counts_bytes, counts_checkpoint, *encoded]

    def encode(self):
        counts = dict()

        while byte := int.from_bytes(self._file.read(1), "big", signed=False):
            if byte not in counts:
                counts[byte] = 0
            counts[byte] += 1
            self._length += 1
            self._data.append(byte)

        counts = {ck: cv for ck, cv in sorted(counts.items(), key=lambda x: x[0])}

        probabilities = {
            b: Fraction(c, self._length) for b, c in counts.items()
        }

        keys = list(probabilities.keys())

        distribution = dict()
        for idx, k in enumerate(keys):
            if idx == 0:
                distribution[k] = (0, probabilities[k])
            else:
                previous = keys[idx - 1]
                distribution[k] = (
                    distribution[previous][1],
                    distribution[previous][1] + probabilities[k]
                )

        low, high = Fraction(0, 1), Fraction(1, 1)

        for idx, byte in enumerate(self._data):
            rng = high - low
            high = low + rng * distribution[byte][1]
            low = low + rng * distribution[byte][0]

        result = self._pack(low, counts)

        return low, result

    @staticmethod
    def _next_byte(file):
        return int.from_bytes(file.read(1), "big", signed=False)

    def decode(self):

        signature_ok = all([
            self._next_byte(self._file) == 0x41,
            self._next_byte(self._file) == 0x52,
            self._next_byte(self._file) == 0x49,
        ])

        if not signature_ok:
            raise Exception("Invalid signature")

        length_of_length = self._next_byte(self._file)
        length_of_table = self._next_byte(self._file)

        length = list()
        for _ in range(length_of_length):
            length.append(self._next_byte(self._file))

        length = int.from_bytes(length, "big", signed=False)

        length_checkpoint = self._next_byte(self._file)
        if length_checkpoint != 0x2e:
            raise Exception("Invalid format")

        counts = dict()
        for _ in range(length_of_table):
            byte = self._next_byte(self._file)
            count = list()
            for __ in range(length_of_length):
                count.append(self._next_byte(self._file))
            count = int.from_bytes(count, "big", signed=False)
            counts[byte] = count

        counts_checkpoint = self._next_byte(self._file)
        if counts_checkpoint != 0x2e:
            raise Exception("Invalid format")

        start = self._next_byte(self._file)
        if start == 0xff:
            code = Fraction(1, 1)
        elif start == 0x00:
            code = list()
            while byte := self._next_byte(self._file):
                code.append(byte)
            code = int.from_bytes(code, "big", signed=False)
            code = Fraction(Decimal(f'0.{code}'))
        else:
            raise Exception("Invalid format")

        probabilities = {
            b: Fraction(c, length) for b, c in counts.items()
        }

        keys = list(probabilities.keys())

        distribution = dict()
        for idx, k in enumerate(keys):
            if idx == 0:
                distribution[k] = (0, probabilities[k])
            else:
                previous = keys[idx - 1]
                distribution[k] = (
                    distribution[previous][1],
                    distribution[previous][1] + probabilities[k]
                )

        decoded = list()

        for _ in range(length):
            for k, v in distribution.items():
                if v[0] <= code < v[1]:
                    decoded.append(k)
                    rng = v[1] - v[0]
                    code = (code - v[0]) / rng
                    break

        return decoded
if __name__ == '__main__':
    sys.set_int_max_str_digits(2**16-1)

    with open('test_input.txt', 'rb') as fin:
        arico = Arico(fin)
        fact, encoded = arico.encode()

        dec ="{0:1024f}".format(Decimal(Decimal(fact.numerator) / Decimal(fact.denominator)))
        print(f"Decimal encoded result: {dec}")

        with open('test_output.ari', 'wb+') as fout:
            fout.write(bytes(encoded))
            print("Wrote to test_output.ari")

    with open('test_output.ari', 'rb') as fin:
        arico = Arico(fin)
        print("Reversing...")
        decoded = arico.decode()

        with open('test_input_recover.txt', 'wb+') as f:
            f.write(bytes(decoded))
            print("Wrote to test_input_recover.txt")
