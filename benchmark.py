import csv
import os
import time
from typing import List


class AricoBenchmark:
    def __init__(self, report_file_name: str, benchmark_source_data: List[dict]):
        self.report_file_name = report_file_name
        self.source_data = benchmark_source_data
        self.header = [
            'file_type',
            'file_name',
            'size_before',
            'size_after',
            'compression_coefficient',
            'execution_time',
        ]

    def run(self):
        benchmark_start = time.time()
        print(f"Arico Benchmark Started. time = {benchmark_start}")
        with open("benchmark_report.csv", "w+", encoding='utf8') as report_file:
            csv_writer = csv.writer(report_file)
            csv_writer.writerow(self.header)

            for data in self.source_data:
                print(f"Processing file {data['type']} ({data['file_name']})")
                start = time.time()

                input_file = data['file_name']
                output_file = input_file + '.ari'

                os.system(f"python arico.py -a -i {input_file} -o {output_file} -w {data['width']}")
                delta = time.time() - start

                size_before = os.path.getsize(input_file)
                size_after = os.path.getsize(output_file)

                compression_coefficient = (size_before - size_after) / size_before * 100.0

                print(f'Results for {data['type']}: size_before = {size_before}, size_after = {size_after}, compression_coefficient = {compression_coefficient}, exec_time = {delta}')

                csv_writer.writerow([
                    data['type'],
                    input_file,
                    size_before,
                    size_after,
                    compression_coefficient,
                    delta
                ])

        print(f"Report is written to {self.report_file_name}")
        print(f"Finished for {time.time() - benchmark_start}")

if __name__ == '__main__':
    benchmark_source_data = [
        {
            'type': 'as',
            'file_name': 'asd',
            'width': 32,
        }
    ]

    AricoBenchmark('/benchmark_report.csv', benchmark_source_data).run()
