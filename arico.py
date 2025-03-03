import argparse
import sys
from fractions import Fraction
from decimal import Decimal
from mpmath import mp, mpf
from typing import List


class Arico:
    def __init__(self, file):
        self._file = file
        self._data: List[int] = list()
        self._length = 0

    @staticmethod
    def _frac_to_float(fraction: Fraction, accuracy: int) -> str:
        num, denom = fraction.numerator, fraction.denominator
        denom_power = len(str(denom))
        result = str(num // denom) + '.'

        mod = num % denom
        for _ in range(accuracy):
            if mod == 0:
                break
            mod_power = len(str(mod))
            diff = denom_power - mod_power
            mod *= 10 ** diff
            if mod < denom:
                mod *= 10

            result += str(mod // denom)
            mod %= denom

        return result

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

        length = list(self._int_to_bytes(self._length))
        length_checkpoint = 0x2e

        counts_bytes = list()
        for k, v in counts.items():
            counts_bytes += [k, *self._int_to_bytes(v, length_of_length)]

        counts_checkpoint = 0x2e

        # decimal_result = str(mpf(mpf(encode_result.numerator) / mpf(encode_result.denominator)))
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
            # power = len(str(code))
            # code = Fraction(code, 10**power)
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

sys.set_int_max_str_digits(2**31 - 1)

if __name__ == '__main__':

    mp.dps = 10**3

    parser = argparse.ArgumentParser(
        prog='arico',
        description='Arico ariphmetical coder',
        epilog='FAST PROTOTYPE'
    )

    parser.add_argument('-a', '--archive', action='store_true')  # positional argument
    parser.add_argument('-e', '--extract', action='store_true')  # option that takes a value
    parser.add_argument('-i', '--in', required=True) # on/off flag
    parser.add_argument('-o', '--out')  # on/off flag

    args = parser.parse_args()

    if args.archive and args.extract:
        raise Exception("You can't specify both -a and -e")

    if args.archive:
        in_file = getattr(args, 'in')
        out_file = getattr(args, 'out')
        if not out_file:
            out_file = in_file + '.ari'

        with open(in_file, 'rb') as fin:
            arico = Arico(fin)
            fact, encoded = arico.encode()

            dec = str(mpf(mpf(fact.numerator) / mpf(fact.denominator)))
            print(f"Decimal encoded result: {dec}")

            with open(out_file, 'wb+') as fout:
                fout.write(bytes(encoded))
                print(f"Archived data has been written to {out_file}")
                exit(0)

    if args.extract:
        in_file = getattr(args, 'in')
        out_file = getattr(args, 'out')
        if not out_file:
            out_file = in_file[-4:]

        with open(in_file, 'rb') as fin:
            arico = Arico(fin)
            decoded = arico.decode()

            with open(out_file, 'wb+') as f:
                f.write(bytes(decoded))
                print(f"Extracted data has been written to {out_file}")
