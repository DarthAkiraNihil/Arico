import csv
import os
import time
from typing import List


class AricoBenchmark:
    def __init__(self, report_file_name: str, benchmark_source_data: dict):
        self.report_file_name = report_file_name
        self.source_data = benchmark_source_data
        self.header = [
            'generalized_type',
            'file_kind',
            'file_name',
            'size_before',
            'size_after',
            'compression_coefficient',
            'execution_time',
        ]

    def run(self):
        benchmark_start = time.time()
        print(f"benchmark: Arico Benchmark Started. time = {benchmark_start}")
        with open("benchmark_report.csv", "w+", newline='', encoding='utf8') as report_file:
            csv_writer = csv.writer(report_file)
            csv_writer.writerow(self.header)

            for generalized_type in self.source_data.keys():
                print(f"[ ===== Processing files of type {generalized_type} ===== ]")
                for data in self.source_data[generalized_type]:
                    print(f"benchmark: Processing file {data['kind']} ({data['file_name']})")
                    start = time.time()

                    input_file = data['file_name']
                    output_file = input_file + '.ari'

                    os.system(f"python arico.py -a -i \"{input_file}\" -o \"{output_file}\" -w {data['width']}")
                    delta = time.time() - start

                    size_before = os.path.getsize(input_file)
                    size_after = os.path.getsize(output_file)

                    compression_coefficient = (size_before - size_after) / size_before * 100.0

                    print(f'benchmark: Results for {data['kind']}: size_before = {size_before}, size_after = {size_after}, compression_coefficient = {compression_coefficient}, exec_time = {delta}')

                    csv_writer.writerow([
                        generalized_type,
                        data['kind'],
                        input_file,
                        size_before,
                        size_after,
                        compression_coefficient,
                        delta
                    ])

        print(f"benchmark: Report is written to {self.report_file_name}")
        print(f"benchmark: Finished for {time.time() - benchmark_start}")

if __name__ == '__main__':
    benchmark_source_data = {
        'text_lorem_ipsum': [
            {
                'kind': 'TXT Lorem Ipsum. 1 Paragraph',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_1p.txt',
                'width': 32,
            },
            {
                'kind': 'TXT Lorem Ipsum. 10 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_10p.txt',
                'width': 32,
            },
            {
                'kind': 'TXT Lorem Ipsum. 100 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_100p.txt',
                'width': 32,
            },
            {
                'kind': 'TXT Lorem Ipsum. 500 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_500p.txt',
                'width': 32,
            },
            {
                'kind': 'TXT Lorem Ipsum. 1000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_1000p.txt',
                'width': 32,
            },
            {
                'kind': 'TXT Lorem Ipsum. 5000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_5000p.txt',
                'width': 32,
            },
            {
                'kind': 'TXT Lorem Ipsum. 10000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_10000p.txt',
                'width': 64,
            },
            {
                'kind': 'TXT Lorem Ipsum. 50000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_50000p.txt',
                'width': 64,
            },
            {
                'kind': 'TXT Lorem Ipsum. 100000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_100000p.txt',
                'width': 128,
            },
            {
                'kind': 'TXT Lorem Ipsum. 500000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_500000p.txt',
                'width': 128,
            },
            {
                'kind': 'TXT Lorem Ipsum. 1000000 Paragraphs',
                'file_name': 'benchmark_data/text_lorem_ipsum/lorem_ipsum_1000000p.txt',
                'width': 256,
            },

        ],
        'text_normal': [
            {
                'kind': 'Text: Абнетт Дэн. Возвышение Хоруса',
                'file_name': 'benchmark_data/text_normal/Абнетт Дэн. Возвышение Хоруса.fb2',
                'width': 32,
            },
            {
                'kind': 'Text: Достоевский Федор. Преступление и наказание',
                'file_name': 'benchmark_data/text_normal/Достоевский Федор.  Преступление и наказание.fb2',
                'width': 32,
            },
            {
                'kind': 'Text: Ланьлинский насмешник. Цветы сливы в золотой вазе, или Цзинь, Пин, Мэй',
                'file_name': 'benchmark_data/text_normal/Ланьлинский насмешник . Цветы сливы в золотой вазе, или Цзинь, Пин, Мэй.txt',
                'width': 32,
            },
        ],
        'image_bmp': [
            {
                'kind': 'BMP Image: Variant 1 (monochrome)',
                'file_name': 'benchmark_data/image_bmp/a_conversation.bmp',
                'width': 64,
            },
            {
                'kind': 'BMP Image: Variant 2 (complex 1)',
                'file_name': 'benchmark_data/image_bmp/chr0me.bmp',
                'width': 64,
            },
            {
                'kind': 'BMP Image: Variant 3 (complex 3)',
                'file_name': 'benchmark_data/image_bmp/just_melony.bmp',
                'width': 64,
            },
        ],
        'image_tiff': [
            {
                'kind': 'TIFF Image: Variant 1 (monochrome)',
                'file_name': 'benchmark_data/image_tiff/a_conversation.tif',
                'width': 64,
            },
            {
                'kind': 'TIFF Image: Variant 2 (complex 1)',
                'file_name': 'benchmark_data/image_tiff/chr0me.tif',
                'width': 64,
            },
            {
                'kind': 'TIFF Image: Variant 3 (complex 3)',
                'file_name': 'benchmark_data/image_tiff/just_melony.tif',
                'width': 64,
            },
        ],
        'image_png': [
            {
                'kind': 'PNG Image: Variant 1 (monochrome)',
                'file_name': 'benchmark_data/image_png/a_conversation.png',
                'width': 32,
            },
            {
                'kind': 'PNG Image: Variant 2 (complex 1)',
                'file_name': 'benchmark_data/image_png/chr0me.png',
                'width': 32,
            },
            {
                'kind': 'PNG Image: Variant 3 (complex 3)',
                'file_name': 'benchmark_data/image_png/just_melony.png',
                'width': 64,
            },
        ],
        'image_jpg': [
            {
                'kind': 'JPG Image: Variant 1 (simple)',
                'file_name': 'benchmark_data/image_jpg/man.jpg',
                'width': 32,
            },
            {
                'kind': 'JPG Image: Variant 2 (simple background 1)',
                'file_name': 'benchmark_data/image_jpg/bangboo.jpg',
                'width': 32,
            },
            {
                'kind': 'JPG Image: Variant 3 (simple background 2)',
                'file_name': 'benchmark_data/image_jpg/ahri.jpg',
                'width': 32,
            },
            {
                'kind': 'JPG Image: Variant 4 (complex 1)',
                'file_name': 'benchmark_data/image_jpg/genos.jpg',
                'width': 32,
            },
            {
                'kind': 'JPG Image: Variant 5 (complex 2)',
                'file_name': 'benchmark_data/image_jpg/drone.jpg',
                'width': 32,
            },
        ],
        'video_mp4': [
            {
                'kind': 'MP4 Video: Variant 1 (slideshow)',
                'file_name': 'benchmark_data/video_mp4/stupid_meme.mp4',
                'width': 32,
            },
            {
                'kind': 'MP4 Video: Variant 2 (with music)',
                'file_name': 'benchmark_data/video_mp4/tbwog_timelapse.mp4',
                'width': 128,
            },
            {
                'kind': 'MP4 Video: Variant 3 (UE Render)',
                'file_name': 'benchmark_data/video_mp4/AShortCGI.mp4',
                'width': 64,
            },
            {
                'kind': 'MP4 Video: Variant 4 (Regular video (but do not open, pls)',
                'file_name': 'benchmark_data/video_mp4/unsafe.mp4',
                'width': 64,
            },
            {
                'kind': 'MP4 Video: Variant 5 (YouTube Movie)',
                'file_name': 'benchmark_data/video_mp4/stupid_meme.mp4',
                'width': 256,
            },
            {
                'kind': 'MP4 Video: Variant 6 (Professional Concert)',
                'file_name': 'benchmark_data/video_mp4/Northlane.Roundhouse.1080pWEB-DL.x264-KiNG_1080p_2020.mp4',
                'width': 256,
            },
        ],
        'music_flac': [
            {
                'kind': 'FLAC Music (lossless): Variant 1',
                'file_name': 'benchmark_data/music_flac/01 Nine Sols.flac',
                'width': 64,
            },
            {
                'kind': 'FLAC Music (lossless): Variant 2',
                'file_name': 'benchmark_data/music_flac/02 Schlag mich.flac',
                'width': 64,
            },
            {
                'kind': 'FLAC Music (lossless): Variant 3',
                'file_name': 'benchmark_data/music_flac/14 Crossing Blades.flac',
                'width': 64,
            },
        ],
        'music_mp3': [
            {
                'kind': 'MP3 Music (lossy): Variant 1',
                'file_name': 'benchmark_data/music_mp3/01. Lumina Aurea.mp3',
                'width': 64,
            },
            {
                'kind': 'MP3 Music (lossy): Variant 2',
                'file_name': 'benchmark_data/music_mp3/01 - Devil Trigger.mp3',
                'width': 64,
            },
            {
                'kind': 'MP3 Music (lossy): Variant 3',
                'file_name': 'benchmark_data/music_mp3/04. Kidnap.mp3',
                'width': 32,
            },
        ],
        'zip': [
            {
                'kind': 'ZIP: Variant 1',
                'file_name': 'benchmark_data/zip/AShortCGI_all.zip',
                'width': 128,
            },
            {
                'kind': 'ZIP: Variant 2',
                'file_name': 'benchmark_data/zip/ffmpeg-6.1.1-essentials_build.zip',
                'width': 64,
            },
            {
                'kind': 'ZIP: Variant 3',
                'file_name': 'benchmark_data/zip/GenosStorExpress.Backend-master.zip',
                'width': 32,
            },
        ],
        'tar': [
            {
                'kind': 'Tarball: Variant 1',
                'file_name': 'benchmark_data/tar/GenosStore.tar',
                'width': 256,
            },
            {
                'kind': 'Tarball: Variant 1',
                'file_name': 'benchmark_data/tar/Memes.tar',
                'width': 64,
            },
            {
                'kind': 'Tarball: Variant 1',
                'file_name': 'benchmark_data/tar/Эмоции Юцке.tar',
                'width': 32,
            },
        ],
        'exe': [
            {
                'kind': 'Executable: Variant 1',
                'file_name': 'benchmark_data/exe/新创Unity.exe',
                'width': 32,
            },
            {
                'kind': 'Executable: Variant 2',
                'file_name': 'benchmark_data/exe/openttd.exe',
                'width': 64,
            },
            {
                'kind': 'Executable: Variant 3',
                'file_name': 'benchmark_data/exe/DoomExplorer.exe',
                'width': 64,
            },
        ],
    }

    AricoBenchmark('/benchmark_report.csv', benchmark_source_data).run()
