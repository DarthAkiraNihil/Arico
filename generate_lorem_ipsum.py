from lorem_text import lorem

sizes = [1, 10, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]

for size in sizes:
    with open(f'benchmark_data/lorem_ipsum_{size}p.txt', 'w+', encoding='utf8') as f:
        for _ in range(size):
            paragraph = ""
            for __ in range(10):
                paragraph += lorem.sentence()

            paragraph += '\n'
            f.write(paragraph)
        print(f"generated for {size}")

