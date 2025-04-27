import argparse
import copy
import sys
from typing import List, BinaryIO


class AricoException(Exception):
    pass


class Arico:
    # _digits = string.digits + string.ascii_letters
    def __init__(self, file, out, width=32, count_scale=0, chunk_size=65536):

        self._file: BinaryIO = file
        self._out: BinaryIO = out
        # self._data: List[int] = list()

        self._length = 0  # Длина исходного потока
        self._read_bits = 0  # Количество прочитанных бит, вспомогательное поле
        self._width = width  # Ширина кодового слова
        self._count_scale = count_scale  # Масштабирование частоты на некоторое количество байт. 0 - масштабирование не нужно

        self._chunk_size = chunk_size

        self._last = 0
        self._chunk_buffer = list()

    # Вспомогательная функция преобразования числа в набор байт
    @staticmethod
    def _int_to_bytes(value: int, desired_length: int = None):

        transformed = [value % 256]
        value >>= 8

        while value != 0:
            transformed.append(value % 256)
            value >>= 8

        # если необходимо, чтобы количество байт было больше, чем требуется - дополняем нулями
        if desired_length is not None:
            while len(transformed) < desired_length:
                transformed.append(0)

        # результат будет записан в обратном порядке, потому необходимо отзеркалить его
        return transformed[::-1]

    # Вспомогательный метод считывания следующего байта в файле как целое число
    @staticmethod
    def _next_byte(file):
        read = file.read(1)
        if not read:
            return -1
        return int.from_bytes(read, "big", signed=False)

    # Вспомогательная функция построения базового распределения
    # Принимает на вход словарь частот
    @staticmethod
    def _build_distribution(counts):
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

        return distribution, keys

    # Вспомогательная функция записи цифры в выходной поток
    # Принимает на вход список-назначение, список заполненности байтов и саму цифру
    @staticmethod
    def _write_digit(dst: List[int], fills: List[int], digit: int, out: BinaryIO):
        offset = 1  # Величина сдвига. Может быть необходима, если основание кодового слова будет другим

        fill = fills[-1]

        # Если после сдвига не будет переполнения байта - просто сдвигаем и записываем цифру
        if fill + offset <= 8:
            dst[-1] = (dst[-1] << offset) + digit
            fills[-1] += offset
        # Иначе излишки сдвигаем в новый разряд, и только затем записываем в конец
        else:
            out.write(bytes([(dst[-1] << (8 - fill)) + (digit >> (offset - 8 + fill))]))
            # dst[-1] = (dst[-1] << (8 - fill)) + (digit >> (offset - 8 + fill))
            dst[-1] = (digit & (2 ** (offset - 8 + fill) - 1))
            fills[-1] = (offset - 8 + fill)
            # fills.append()

    # Вспомогательный метод чтения следующей цифры из входного потока
    def _read_digit(self):

        # Если достигли конца файла - возвращаем -1 - невозможное значение, которое будет являться флагом конца файла
        if not self._chunk_buffer:
            self._chunk_buffer = self._file.read(self._chunk_size)
            if not self._chunk_buffer:
                return -1

        # Считываем 1 бит, т.к. основание системы счисления - 2
        length = 1

        value = self._chunk_buffer[0]

        # Если мы ещё не считали полный байт, то из считанного байта извлекаем нужный разряд,
        # перемещаем указатель в файле на 1 позицию назад, и возвращаем считанный разряд
        if self._read_bits + length <= 8:
            self._read_bits += length
            result = (value & ((2 ** length - 1) << (8 - self._read_bits))) >> (8 - self._read_bits)
            if self._read_bits < 8:
                pass
            else:
                self._chunk_buffer = self._chunk_buffer[1:]
                self._read_bits = 0
            return result

        # Иначе выясняем, сколько бит надо взять из текущего байта и сколько - из следующего
        remaining = 8 - self._read_bits
        taken = (self._read_bits + length) - 8

        result = value & (2 ** remaining - 1)

        # Чтение следующего байта, откуда заимствуем разряды
        if len(self._chunk_buffer) == 1:
            self._chunk_buffer = self._file.read(self._chunk_size)
            if not self._chunk_buffer:
                taken_value = 0
            else:
                taken_value = self._chunk_buffer[0]
        else:
            self._chunk_buffer = self._chunk_buffer[1:]
            taken_value = self._chunk_buffer[0]

        # Из нового считанного байта извлекаем нужный разряд,
        # перемещаем указатель в файле на 1 позицию назад, и возвращаем считанный разряд
        result = (result << taken) + (((2 ** taken - 1) << (8 - taken)) & taken_value) >> (8 - taken)

        # self._file.seek(-1, 1)
        self._read_bits = taken

        return result

    # Метод упаковки закодированного сообщения в итоговый набор байт с требуемой структурой
    def _pack_header(self, counts):
        # Сигнатура
        signature = [0x41, 0x52, 0x49]  # ARI

        # Длина длины и ширины кодового слова
        length_of_length = (self._length.bit_length() + 7) // 8
        # length_of_table = len(counts.keys()) - 1
        length_of_width = (self._width.bit_length() + 7) // 8

        length = list(self._int_to_bytes(self._length))
        width = list(self._int_to_bytes(self._width))
        last = self._last  # Записываем последний бит исходного потока для успешного декодирования

        length_checkpoint = 0x2e
        # Упаковка словаря
        counts_bytes = list()
        for char in range(256):  # Больше 256 символов быть не может
            if self._count_scale == 0:
                if char in counts:
                    char_bytes = self._int_to_bytes(counts[char], length_of_length)
                else:  # Если символа нет - записываем 0 как частоту
                    char_bytes = self._int_to_bytes(0, length_of_length)
            else:
                # Если было указано масштабирование частоты на количество байт - выполняем преобразование
                if char in counts:
                    char_bytes = self._int_to_bytes((counts[char] // self._length) * (2 ** (8 * self._count_scale) - 1), self._count_scale)
                else:  # Если символа нет - записываем 0 как частоту
                    char_bytes = self._int_to_bytes(0, self._count_scale)
            counts_bytes += char_bytes

        counts_checkpoint = 0x2e

        return [
            *signature,
            length_of_length,
            # length_of_table,
            length_of_width,
            *length,
            *width,
            self._count_scale,
            last,
            length_checkpoint,
            *counts_bytes,
            counts_checkpoint,
            # *encode_result
        ]

    def encode(self):  # noqa: C901
        counts = dict()

        # Считывание данных с файла и построение статистики
        while True:
            data = self._file.read(self._chunk_size)
            if not data:
                break
            self._last = data[-1]

            for elem in data:
                if elem not in counts:
                    counts[elem] = 0
                counts[elem] += 1
                self._length += 1

        # Сортировка словаря по ключам с масштабированием по ширине кодового слова
        scaling = 2 ** self._width
        counts = {ck: cv for ck, cv in sorted(counts.items(), key=lambda x: x[0])}
        pure_counts = copy.deepcopy(counts)
        counts = {ck: cv * scaling // self._length for ck, cv in counts.items()}

        # Построение распределения
        distribution, keys = self._build_distribution(counts)

        # Коэффициент масштаба
        scale = distribution[keys[-1]][1]

        # вспомогательные массивы для записи результата кодирования
        result = [0]
        fills = [0]

        low, high = 0, scale + 1
        power_loss = 0  # Количество бит исчезновения порядка

        written = 0

        # Кодирование

        self._file.seek(0)

        packed = self._pack_header(pure_counts)
        self._out.write(bytes(packed))

        while chunk := self._file.read(self._chunk_size):
            for byte in chunk:

                # Пересчёт верхних и нижних границ в зависимости от текущего байта
                rng = high - low + 1
                high = low + rng * distribution[byte][1] // scale - 1
                low = low + rng * distribution[byte][0] // scale

                # Запись результата кодирования текущего байта
                while True:

                    # Извлечение старших разрядов
                    elder_low = low >> (self._width - 1)
                    elder_high = high >> (self._width - 1)

                    if elder_high == elder_low:  # При совпадении - запись совпадающего бита в выходной поток
                        self._write_digit(result, fills, elder_low, self._out)
                        written += 1
                        # Если имело место исчезновение порядка - выталкиваем инвертированный старший бит верхней границы в выходной поток столько раз, сколько было исчезновений
                        while power_loss != 0:
                            k = ((high ^ (2 ** self._width - 1)) & (2 ** self._width))
                            self._write_digit(result, fills, k, self._out)
                            written += 1
                            power_loss -= 1
                    # Иначе возможно исчезновение порядка
                    # Если условия исчезновения выполняются - сдвигаем все разряды, кроме первого,
                    # на 1 влево и дописываем в верхнюю границу максимальную цифру текущей системы счисления
                    # Не забываем увеличить счётчик исчезновения порядка
                    elif low & (2 ** (self._width - 1)) == 2 ** self._width - 1 and high & (2 ** self._width - 1) == 0:
                        low &= (2 ** self._width - 1) - (2 ** (self._width - 1)) - (2 ** (self._width - 2))
                        high |= (2 ** self._width - 1)
                        power_loss += 1
                    else:  # Иначе никаких действий предпринимать не надо
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
        self._write_digit(result, fills, elder_low, self._out)
        written += 1
        while power_loss != 0:
            k = ((low ^ (2 ** self._width - 1)) & (2 ** (self._width - 1))) >> 4
            self._write_digit(result, fills, k, self._out)
            written += 1
            power_loss -= 1

        if written % self._width == 0:
            for _ in range(self._width):
                self._write_digit(result, fills, 0, self._out)
        else:
            while written % self._width != 0:
                self._write_digit(result, fills, 0, self._out)
                written += 1
            for _ in range(self._width):
                self._write_digit(result, fills, 0, self._out)

        # Упаковка в байты

        return

    def decode(self):  # noqa: C901
        # Проверка сигнатуры и считывание длин
        signature_ok = all([
            self._next_byte(self._file) == 0x41,
            self._next_byte(self._file) == 0x52,
            self._next_byte(self._file) == 0x49,
        ])

        if not signature_ok:
            raise AricoException("Error: Invalid signature")

        # Считывание длин (в частности - длины исходного потока и ширины кодового слова), и последнего байта исходной последовательности
        length_of_length = self._next_byte(self._file)
        # length_of_table = self._next_byte(self._file) + 1
        length_of_width = self._next_byte(self._file)

        length = list()
        for _ in range(length_of_length):
            length.append(self._next_byte(self._file))

        length = int.from_bytes(length, "big", signed=False)

        width = list()
        for _ in range(length_of_width):
            width.append(self._next_byte(self._file))

        self._count_scale = self._next_byte(self._file)
        last = self._next_byte(self._file)

        self._width = int.from_bytes(width, "big", signed=False)
        length_checkpoint = self._next_byte(self._file)
        # Должен дойти до контрольной точки
        if length_checkpoint != 0x2e:
            raise AricoException(f"Error: Invalid format length_checkpoint not found, found byte = {length_checkpoint}")

        # Считывание частот
        counts = dict()
        for char in range(256):
            count = list()
            for __ in range(length_of_length):
                count.append(self._next_byte(self._file))
            count = int.from_bytes(count, "big", signed=False)
            if count != 0:  # Нет смысла записывать символ с нулевой частотой
                if self._count_scale == 0:
                    counts[char] = count
                else:  # Если имело место масштабирование частоты по количеству байт на них, то восстанавливаем её
                    counts[char] = (count * length) // (2 ** (8 * self._count_scale) - 1)

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
        distribution, keys = self._build_distribution(counts)

        scale = distribution[keys[-1]][1]
        decode_result: int = 0

        # Установка нижней и верхней границы
        low, high = 0, scale + 1

        eof = False  # Флаг конца файла

        rd = 0  # Количество раскодированных байт

        # Декодирование
        while not eof and rd < length:

            # Определение закодированного байта
            rng = high - low + 1
            value = ((code - low + 1) * scale - 1) // rng

            for k, v in distribution.items():
                if v[0] <= value < v[1]:
                    decode_result = k
                    self._out.write(bytes([k]))
                    # decode_result.append(k)
                    break

            # Пересчёт границ
            high = low + rng * distribution[decode_result][1] // scale - 1
            low = low + rng * distribution[decode_result][0] // scale

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
        self._out.seek(-1, 1)
        self._out.write(bytes([last]))
        return


if __name__ == '__main__':  # noqa: C901

    # Считывание аргументов командной строки
    parser = argparse.ArgumentParser(
        prog='arico',
        description='Arico arithmetical coder and decoder',
        epilog='By Akira Nihil'
    )

    parser.add_argument('-a', '--archive', action='store_true')
    parser.add_argument('-e', '--extract', action='store_true')
    parser.add_argument('-i', '--in', required=True)
    parser.add_argument('-o', '--out')
    parser.add_argument('-w', '--width', type=int, default=32)
    parser.add_argument('-s', '--scale', type=int, default=0)
    parser.add_argument('-c', '--chunk_size', type=int, default=65536)

    args = parser.parse_args()

    # Нельзя одновременно и распаковать, и запаковать
    if args.archive and args.extract:
        raise Exception("You can't specify both -a and -e")

    # Если длина кодового слова меньше 2 - то ошибка, так как слишком коротко
    if args.width < 2:
        print("Code word width is too small. Enter at least 2!")
        sys.exit(1)

    if args.chunk_size < 1:
        print("Chunk size is too small. Enter at least 1!")
        sys.exit(2)

    if args.chunk_size > 4 * (1024 ** 2):
        print("Warning: chunk size greater than 4MB may cause encode/decode performance issues and RAM running out")

    # Большая длина кодового слова может привести к проблемам с точностью и производительностью
    if args.width > 256:
        print("Warning: high values of code word width may cause encode/decode accuracy and performance issues")

    # Ширина вшивается в заголовок сжатого файла, потому нет смысла её указывать для распаковки
    if args.width and args.extract:
        print("Warning: width in extraction process is ignored")

    if args.scale != 0:
        print(f"Using frequency scale to {args.scale} bytes")
    else:
        print("No frequency scaling is used")

    # Величина масштабирования частоты вшивается в заголовок сжатого файла, потому нет смысла её указывать для распаковки
    if args.scale and args.extract:
        print("Warning: frequency scaling in extraction process is ignored")

    if args.archive:
        # Открытие файла и кодирование
        in_file = getattr(args, 'in')
        out_file = getattr(args, 'out')
        if not out_file:
            out_file = in_file + '.ari2'

        with open(in_file, 'rb') as fin, open(out_file, 'wb+') as fout:
            arico = Arico(fin, fout, args.width, args.scale)
            try:
                arico.encode()
                print(f"Archived data has been written to {out_file}")
                sys.exit(0)
            # Если ошибка - аварийное завершение программы
            except Exception as e:
                print(e)
                sys.exit(255)

    if args.extract:
        # Открытие файла и декодирование
        in_file = getattr(args, 'in')
        out_file = getattr(args, 'out')

        if not out_file:
            out_file = in_file[-4:]

        with open(in_file, 'rb') as fin, open(out_file, 'wb+') as f:
            arico = Arico(fin, f, args.width, args.scale)
            try:
                arico.decode()
                print(f"Extracted data has been written to {out_file}")
                sys.exit(0)
            # Если ошибка - аварийное завершение программы
            except Exception as e:
                print(e)
                sys.exit(255)
