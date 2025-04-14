import argparse
import copy
import sys
from ctypes import windll
from fractions import Fraction
from decimal import Decimal
from typing import List, BinaryIO
import string


class AricoException(Exception): ...

class Arico:
    _digits = string.digits + string.ascii_letters
    def __init__(self, file, width):

        self._file: BinaryIO = file
        self._data: List[int] = list()

        self._length = 0
        self._read_bits = 0
        self._width = width


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

    # Вспомогательный метод считывания следующего байта в файле как целое число
    @staticmethod
    def _next_byte(file):
        read = file.read(1)
        print(f"READ VAL: {read}")
        if not read:
            return -1
        return int.from_bytes(read, "big", signed=False)

    def _write_digit(self, dst: List[int], fills: List[int], digit: int):
        offset = 1
        print(f"writing digit: {digit}")

        fill = fills[-1]

        if fill + offset <= 8:
            dst[-1] = (dst[-1] << offset) + digit
            fills[-1] += offset
        else:
            dst[-1] = (dst[-1] << (8 - fill)) + (digit >> (offset - 8 + fill))
            dst.append(digit & (2 ** (offset - 8 + fill) - 1))
            fills.append((offset - 8 + fill))

    def _read_digit(self):

        read = self._file.read(1)
        if not read:
            return -1

        length = 1

        value = int.from_bytes(read, "big", signed=False)

        if self._read_bits + length <= 8:
            self._read_bits += length
            result = (value & ((2 ** length - 1) << (8 - self._read_bits))) >> (8 - self._read_bits)
            if self._read_bits < 8:
                self._file.seek(-1, 1)
            else:
                self._read_bits = 0
            return result

        remaining = 8 - self._read_bits
        taken = (self._read_bits + length) - 8

        result = value & (2 ** remaining - 1)

        read = self._file.read(1)
        if not read:
            taken_value = 0
        else:
            taken_value = int.from_bytes(read, "big", signed=False)

        result = (result << taken) + (((2 ** taken - 1) << (8 - taken)) & taken_value) >> (8 - taken)

        self._file.seek(-1, 1)
        self._read_bits = taken

        return result

    # Метод упаковки закодированного сообщения в итоговый набор байт с требуемой структурой
    def _pack(self, encode_result, counts):
        # Сигнатура
        signature = [0x41, 0x52, 0x49]  # ARI

        # Длина длины, словаря и ширины кодового слова
        length_of_length = (self._length.bit_length() + 7) // 8
        length_of_table = len(counts.keys()) - 1
        length_of_width = (self._width.bit_length() + 7) // 8

        length = list(self._int_to_bytes(self._length))
        width = list(self._int_to_bytes(self._width))
        length_checkpoint = 0x2e
        # Упаковка словаря
        counts_bytes = list()
        for k, v in counts.items():
            counts_bytes += [k, *self._int_to_bytes(v, length_of_length)]

        counts_checkpoint = 0x2e

        return [
            *signature,
            length_of_length,
            length_of_table,
            length_of_width,
            *length,
            *width,
            length_checkpoint,
            *counts_bytes,
            counts_checkpoint,
            *encode_result
        ]

    def encode(self):
        counts = dict()

        # Считывание данных с файла и построение статистики
        while True:
            data = self._file.read(1)
            if not data:
                break
            byte = int.from_bytes(data, "big", signed=False)
            if byte not in counts:
                counts[byte] = 0
            counts[byte] += 1
            self._length += 1
            self._data.append(byte)

        print(self._length)
        # Сортировка словаря по ключам с масштабированием по ширине кодового слова
        scaling = 2 ** self._width
        counts = {ck: cv for ck, cv in sorted(counts.items(), key=lambda x: x[0])}
        pure_counts = copy.deepcopy(counts)
        counts = {ck: cv * scaling // len(self._data) for ck, cv in counts.items()}

        # Построение распределения
        keys = list(counts.keys())
        print(keys)

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

        # Коэффициент масштаба
        scale = distribution[keys[-1]][1]

        print(distribution)

        # вспомогательные массивы для записи результата кодирования
        result = [0]
        fills = [0]

        low, high = 0, scale + 1
        power_loss = 0 # Количество бит исчезновения порядка

        written = 0

        # Кодирование
        for idx, byte in enumerate(self._data):

            # Пересчёт верхних и нижних границ в зависимости от текущего байта
            rng = high - low + 1
            high = low + rng * distribution[byte][1] // scale - 1
            low = low + rng * distribution[byte][0] // scale

            # Запись результата кодирования текущего байта
            while True:

                # Извлечение старших разрядов
                elder_low = low >> (self._width - 1)
                elder_high = high >> (self._width - 1)


                if elder_high == elder_low: # При совпадении - запись совпадающего бита в выходной поток\
                    self._write_digit(result, fills, elder_low)
                    written += 1
                    # Если имело место исчезновение порядка - выталкиваем инвертированный старший бит верхней границы в выходной поток столько раз, сколько было исчезновений
                    while power_loss != 0:
                        k = ((high ^ (2 ** self._width - 1)) & (2 ** self._width))
                        self._write_digit(result, fills, k)
                        written += 1
                        power_loss -= 1
                else:
                    # Иначе возможно исчезновение порядка
                    # Если условия исчезновения выполняются - сдвигаем все разряды, кроме первого,
                    # на 1 влево и дописываем в верхнюю границу максимальную цифру текущей системы счисления
                    # Не забываем увеличить счётчик исчезновения порядка
                    if low & (2 ** (self._width - 1)) == 2 ** self._width - 1 and high & (2 ** self._width - 1) == 0:
                        low &= (2 ** self._width - 1) - (2 ** (self._width - 1)) - (2 ** (self._width - 2))
                        high |= (2 ** self._width - 1)
                        power_loss += 1
                    else: # Иначе никаких действий предпринимать не надо
                        break

                # Смещение границ на 1
                low <<= 1
                high <<= 1
                high |= 1

                # Отсечение лишних разрядов
                low &= (2 ** self._width - 1)
                high &= (2 ** self._width - 1)

        # Выталкивание оставшихся бит исчезновения порядка в выходной поток
        elder_low = low >> (self._width - 1)
        self._write_digit(result, fills, elder_low)
        written += 1
        while power_loss != 0:
            k = ((low ^ (2 ** self._width - 1)) & (2 ** (self._width - 1))) >> 4
            self._write_digit(result, fills, k)
            written += 1
            power_loss -= 1

        print(result)
        if written % self._length == 0:
            for _ in range(self._width):
                self._write_digit(result, fills, 0)
        else:
            while written % self._width != 0:
                self._write_digit(result, fills, 0)
                written += 1
            for _ in range(self._width):
                self._write_digit(result, fills, 0)

        print(result)
        print(fills)
        print(list(map(lambda x: bin(x)[2:], result)))

        # Упаковка в байты
        packed = self._pack(result, pure_counts)

        return packed

    def decode(self):
        # Проверка сигнатуры и считывание длин
        signature_ok = all([
            self._next_byte(self._file) == 0x41,
            self._next_byte(self._file) == 0x52,
            self._next_byte(self._file) == 0x49,
        ])

        if not signature_ok:
            raise AricoException("Error: Invalid signature")

        # Считывание длин (в частности - длины исходного потока и ширины кодового слова)
        length_of_length = self._next_byte(self._file)
        length_of_table = self._next_byte(self._file) + 1
        length_of_width = self._next_byte(self._file)

        length = list()
        for _ in range(length_of_length):
            length.append(self._next_byte(self._file))

        length = int.from_bytes(length, "big", signed=False)

        width = list()
        for _ in range(length_of_width):
            width.append(self._next_byte(self._file))

        self._width = int.from_bytes(width, "big", signed=False)
        print(f"W: {self._width}")
        length_checkpoint = self._next_byte(self._file)
        # Должен дойти до контрольной точки
        if length_checkpoint != 0x2e:
            raise AricoException(f"Error: Invalid format length_checkpoint not found, found byte = {length_checkpoint}")

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
            raise AricoException(f"Error: Invalid format counts_checkpoint not found, found byte = {counts_checkpoint}")

        # Считывание закодированного числа и представление в виде кода
        code = 0

        it = 0
        while it < self._width:
            dig = self._read_digit()
            if dig == -1:
                break
            else:
                code = (code << 1) | dig
                it += 1

        # Если во время чтения было считано меньше ширины кодового слова - дополнить нулями до помещения в длину
        if it != self._width:
            while it < self._width:
                code <<= 1

        # Сортировка словаря по ключам
        scaling = 2 ** self._width
        counts = {ck: cv for ck, cv in sorted(counts.items(), key=lambda x: x[0])}
        counts = {ck: cv * scaling // length for ck, cv in counts.items()}

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
        decoded = list()

        # Установка нижней и верхней границы
        low, high = 0, scale + 1

        eof = False # Флаг конца файла

        rd = 0 # Количество раскодированных байт

        # Декодирование
        while not eof and rd < length:

            # Определение закодированного байта
            rng = high - low + 1
            value = ((code - low + 1) * scale - 1) // rng

            for k, v in distribution.items():
                if v[0] <= value < v[1]:
                    print(f"recognized: {k}, l: {v[0]}, v: {value}, h: {v[1]}")
                    decoded.append(k)
                    break

            # Пересчёт границ
            high = low + rng * distribution[decoded[-1]][1] // scale - 1
            low = low + rng * distribution[decoded[-1]][0] // scale

            # Классические тесты на исчезновение порядка и считывание следующей цифры
            while True:

                elder_low = low >> (self._width - 1)
                elder_high = high >> (self._width - 1)

                if elder_high == elder_low:
                    pass
                elif low & (2 ** (self._width - 1)) == 2 ** (self._width - 1) and high & (2 ** (self._width - 1)) == 0:
                    low &= (2 ** self._width - 1) - (2 ** (self._width - 1)) - (2 ** (self._width - 2))
                    high |= (2 ** (self._width - 1))
                    code ^= (2 ** (self._width - 1))
                else:
                    break

                # Сдвиг и считывание следующей цифры
                low <<= 1
                high <<= 1
                high |= 1

                low &= (2 ** self._width - 1)
                high &= (2 ** self._width - 1)

                next_digit = self._read_digit()
                if next_digit == -1:
                    # Если файл закончился, то завершить декодирование
                    # code <<= 1
                    print("eof reached")
                    eof = True
                    break

                # Иначе добавить считанную цифру
                code = (code << 1) | next_digit
                # Отсечение лишних разрядов
                code &= (2 ** self._width - 1)

            rd += 1

        if rd == length:
            print("OK")
        else:
            print("FAIL")
        print(decoded)
        return decoded

sys.set_int_max_str_digits(2**31 - 1)

if __name__ == '__main__':

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
            arico = Arico(fin, 64)
            encoded = arico.encode()

            print(encoded)
            with open(out_file, 'wb+') as fout:
                fout.write(bytes(encoded))
                print(f"Archived data has been written to {out_file}")
                exit(0)

    if args.extract:
        # Открытие файла и декодирование
        in_file = getattr(args, 'in')
        out_file = getattr(args, 'out')

        if not out_file:
            out_file = in_file[-4:]

        with open(in_file, 'rb') as fin:
            arico = Arico(fin, 64 )
            decoded = arico.decode()

            with open(out_file, 'wb+') as f:
                f.write(bytes(decoded))
                print(f"Extracted data has been written to {out_file}")
