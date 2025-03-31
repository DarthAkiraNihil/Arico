import argparse
import copy
import math
import sys
from fractions import Fraction
from decimal import Decimal
from mpmath import mp, mpf, clsin
from typing import List
import string

class Arico:
    _digits = string.digits + string.ascii_letters
    def __init__(self, file):


        self._file = file
        self._data: List[int] = list()
        self._length = 0
        self._base = 10


    @classmethod
    def int2base(cls, x, base):
        if x < 0:
            sign = -1
        elif x == 0:
            return cls._digits[0]
        else:
            sign = 1

        x *= sign
        digits = []

        while x:
            digits.append(cls._digits[int(x % base)])
            x = int(x // base)

        if sign < 0:
            digits.append('-')

        digits.reverse()

        return ''.join(digits)

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

    # Вспомогательная функция преобразования числа в набойрбайт
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

    # Метод упаковки закодированного сообщения в итоговый набор байт с требуемой структурой
    def _pack(self, encode_result, counts):
        # Сигнатура
        signature = [0x41, 0x52, 0x49]  # ARI

        # Длина длины и словаря
        length_of_length = (self._length.bit_length() + 7) // 8
        length_of_table = len(counts.keys())

        length = list(self._int_to_bytes(self._length))
        length_checkpoint = 0x2e
        # Упаковка словаря
        counts_bytes = list()
        for k, v in counts.items():
            counts_bytes += [k, *self._int_to_bytes(v, length_of_length)]

        counts_checkpoint = 0x2e
        # Преобразование дроби в вещественное число
        # decimal_result = str(mpf(mpf(encode_result.numerator) / mpf(encode_result.denominator)))
        decimal_result = "{0:f}".format(Decimal(encode_result.numerator) / Decimal(encode_result.denominator))
        _solid, _partial = decimal_result.split('.')[0], decimal_result.split('.')[1]

        if int(_solid) == 0:
            encoded = [0x00]
        else:
            encoded = [0xff]

        # Преобразование дробной части в набор байт
        encoded += self._int_to_bytes(int(_partial))

        return [*signature, length_of_length, length_of_table, *length, length_checkpoint, *counts_bytes, counts_checkpoint, *encoded]

    # Метод кодирования сообщения
    def encode(self):
        counts = dict()

        # Считывание данных с файла и построение статистики
        while byte := int.from_bytes(self._file.read(1), "big", signed=False):
            if byte not in counts:
                counts[byte] = 0
            counts[byte] += 1
            self._length += 1
            self._data.append(byte)

        # Сортировка словаря по ключам
        counts = {ck: cv for ck, cv in sorted(counts.items(), key=lambda x: x[0])}

        # Построение вероятностей
        probabilities = {
            b: Fraction(c, self._length) for b, c in counts.items()
        }

        # Построение распределения
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

        # Представление начала и конца интервала в виде дробей
        low, high = Fraction(0, 1), Fraction(1, 1)

        # Кодирование
        for idx, byte in enumerate(self._data):
            rng = high - low
            high = low + rng * distribution[byte][1]
            low = low + rng * distribution[byte][0]

        # Упаковка в байты
        result = self._pack(low, counts)

        return low, result

    # Вспомогательный метод считывания следующего байта в файле как целое число
    @staticmethod
    def _next_byte(file):
        return int.from_bytes(file.read(1), "big", signed=False)

    @classmethod
    def _normalize(cls, number_repr: List[int]):
        for idx in range(len(number_repr) - 1, 0, -1):
            elder = number_repr[idx] >> 8
            number_repr[idx] &= 0xFF
            number_repr[idx - 1] += elder

        elder = number_repr[0] >> 8
        number_repr[0] &= 0xFF
        if elder == 0:
            return number_repr

        return [elder, *number_repr]

    @classmethod
    def _append_with_alignment(cls, dst: List[int], byte: int):
        normal, rem = byte // 2, byte % 2

        doubled = list(map(lambda x: x << 1, dst))
        res = cls._normalize(doubled)

        for _ in range(normal - 1):

            for idx in range(len(dst) -1, -1, -1):
                res[idx] += dst[idx]
            res = cls._normalize(res)

        res[-1] += rem
        return cls._normalize(res)

    # Функция декодирования сообщения
    def decode(self):

        # Проверка сигнатуры и считывание длин
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
        # Должен дойти до контрольной точки
        if length_checkpoint != 0x2e:
            raise Exception("Invalid format")

        # Считывание частот
        counts = dict()
        for _ in range(length_of_table):
            byte = self._next_byte(self._file)
            count = list()
            for __ in range(length_of_length):
                count.append(self._next_byte(self._file))
            count = int.from_bytes(count, "big", signed=False)
            counts[byte] = count

        counts_checkpoint = self._next_byte(self._file)
        # Должен дойти до контрольной точки
        if counts_checkpoint != 0x2e:
            raise Exception("Invalid format")

        # Считывание закодированного числа и представление в виде кода
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

        # Построение вероятностей и интервала кодирования
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

        # Декодирование
        for _ in range(length):
            for k, v in distribution.items():
                if v[0] <= code < v[1]:
                    decoded.append(k)
                    rng = v[1] - v[0]
                    code = (code - v[0]) / rng
                    break

        return decoded

    # Метод упаковки закодированного сообщения в итоговый набор байт с требуемой структурой
    def _pack_solid(self, encode_result, counts):
        # Сигнатура
        signature = [0x41, 0x52, 0x49]  # ARI

        # Длина длины и словаря
        length_of_length = (self._length.bit_length() + 7) // 8
        length_of_table = len(counts.keys())

        length = list(self._int_to_bytes(self._length))
        length_checkpoint = 0x2e
        # Упаковка словаря
        counts_bytes = list()
        for k, v in counts.items():
            counts_bytes += [k, *self._int_to_bytes(v, length_of_length)]

        counts_checkpoint = 0x2e
        # Преобразование дроби в вещественное число

        return [
            *signature,
            length_of_length,
            length_of_table,
            *length,
            length_checkpoint,
            self._base,
            *counts_bytes,
            counts_checkpoint,
            *encode_result
        ]



    def encode_solid(self):
        counts = dict()

        # Считывание данных с файла и построение статистики
        while byte := int.from_bytes(self._file.read(1), "big", signed=False):
            if byte not in counts:
                counts[byte] = 0
            counts[byte] += 1
            self._length += 1
            self._data.append(byte)

        # Сортировка словаря по ключам
        scaling = self._base ** 23
        counts = {ck: cv for ck, cv in sorted(counts.items(), key=lambda x: x[0])}
        pure_counts = copy.deepcopy(counts)
        counts = {ck: cv * scaling // len(self._data) for ck, cv in counts.items()}

        # Построение распределения
        keys = list(counts.keys())

        distribution = dict()
        for idx, k in enumerate(keys):
            if idx == 0:
                distribution[k] = (0, counts[k])
            else:
                previous = keys[idx - 1]
                distribution[k] = (
                    distribution[previous][1],
                    distribution[previous][1] + counts[k]
                )

        scale = distribution[keys[-1]][1]

        print(distribution)
        x = ""
        result = [0]
        fills = [0]
        # Представление начала и конца интервала в виде дробей
        low, high = 0, scale + 1
        power_loss = 0
        # Кодирование
        for idx, byte in enumerate(self._data):

            rng = high - low + 1
            high = low + rng * distribution[byte][1] // scale - 1
            low = low + rng * distribution[byte][0] // scale

            # print(f"LO: {low}, HI: {high}")

            # low_based = int2base(low, self._base)
            # high_based = int2base(high, self._base)
            # minle = max(len(low_based), len(high_based))
            # low_based = low_based.zfill(minle)
            # high_based = high_based.zfill(minle)

            while True:

                print(f"JAJAJ LO: {self.int2base(low, self._base)}, HI: {self.int2base(high, self._base)}, LELO: {len(self.int2base(low, self._base))}, LEHI: {len(self.int2base(high, self._base))}")

                # low_based = int2base(low, self._base).ljust(24, '0') #if low != 0 else '0' * 24
                # high_based = int2base(high, self._base).ljust(24, str(self._base - 1))

                # low_based = low_based.ljust(24, '0')
                # high_based = high_based.ljust(24, str(self._base - 1))

                low_based = self.int2base(low, self._base)
                high_based = self.int2base(high, self._base)
                minle = max(len(low_based), len(high_based))
                low_based = low_based.zfill(minle).ljust(24, '0')
                high_based = high_based.zfill(minle).ljust(24, self._digits[self._base - 1])

                print(f"LO: {low_based}, HI: {high_based}")
                elder_low = low_based[0]
                elder_high = high_based[0]
                print(f"ELO: {elder_low}, EHI: {elder_high}")

                if elder_high == elder_low:
                    print(f"EQ: {elder_high}")
                    x += str(elder_low)
                    result = self._append_with_alignment(result, int(elder_low, self._base))
                    while power_loss != 0:
                        # k = ((high ^ 0xFFFFFF) & 0x800000)
                        x += str(self._base - 1 - int(elder_high, self._base))
                        # byte = self._base - 1 if elder_high
                        result = self._append_with_alignment(result, self._base - 1 - int(elder_high, self._base))
                        power_loss -= 1
                else:
                    if int(low_based[1], self._base) == self._base - 1 and int(high_based[1], self._base) == 0 and (abs(int(elder_low, self._base) - int(elder_high, self._base)) == 1):
                        print("LOSS")
                        low_based = low_based[0] + low_based[2:] + '0'
                        high_based = high_based[0] + high_based[2:] + self._digits[self._base - 1]
                        # low &= 0x3FFFFFF
                        # high &= 0x400000
                        power_loss += 1
                    else:
                        # low = int(low_based, self._base)
                        # high = int(high_based, self._base)
                        break

                # low_based = low_based[1:].ljust(24, '0')
                # high_based = high_based[1:].ljust(24, str(self._base - 1))
                low = int(low_based[1:].ljust(24, '0'), self._base)
                high = int(high_based[1:].ljust(24, self._digits[self._base - 1]), self._base)

                print(f"ALO: {low_based[1:].ljust(24, '0')}, HI: {high_based[1:].ljust(24, self._digits[self._base - 1])}")
                #print(f"ALO: {low}, AHI: {high}")

        print(x.zfill(8* (len(x) // 8 + 1)))
        print(result)
        print(list(map(lambda y: bin(y)[2:].zfill(8), result)))

        # Упаковка в байты
        result_ = self._pack_solid(result, pure_counts)
        print(result_)

        return low, None

    def decode_solid(self):
        pass

sys.set_int_max_str_digits(2**31 - 1)

if __name__ == '__main__':
    mp.dps = 10**3

    # Считывание аргументов командной строки
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

    # Нельзя одновременно и распаковать, и запаковать
    if args.archive and args.extract:
        raise Exception("You can't specify both -a and -e")

    if args.archive:
        # Открытие файла и кодирование
        in_file = getattr(args, 'in')
        out_file = getattr(args, 'out')
        if not out_file:
            out_file = in_file + '.ari2'

        with open(in_file, 'rb') as fin:
            arico = Arico(fin)
            arico.encode_solid()
            # fact, encoded = arico.encode()
            #
            # dec = str(mpf(mpf(fact.numerator) / mpf(fact.denominator)))
            # print(f"Decimal encoded result: {dec}")
            #
            # with open(out_file, 'wb+') as fout:
            #     fout.write(bytes(encoded))
            #     print(f"Archived data has been written to {out_file}")
            #     exit(0)

    if args.extract:
        # Открытие файла и декодирование
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
