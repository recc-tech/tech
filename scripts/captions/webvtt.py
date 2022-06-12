from __future__ import annotations
from datetime import datetime
from typing import Callable


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


class Caption:
    def __init__(self, num: int, start: datetime, end: datetime, text: str) -> Caption:
        self.num = num
        self.start_time = start
        self.end_time = end
        self.text = text
    
    @staticmethod
    def parse(chunk: str) -> Caption:
        lines = chunk.split("\n")
        _assert(
            len(lines) == 3,
            f"Expected three lines per caption, but have {len(lines)} lines in the following caption:\n{chunk}"
        )
        num = int(lines[0])
        times = lines[1].split(" --> ")
        _assert(len(times) == 2, f"Expected a start and end time, but received '{lines[1]}'.")
        start = datetime.strptime(times[0], "%H:%M:%S.%f")
        end = datetime.strptime(times[1], "%H:%M:%S.%f")
        text = lines[2]
        return Caption(num, start, end, text)
    
    def __str__(self):
        # Chop off the last three digits of the microseconds component
        start_str = self.start_time.strftime("%H:%M:%S.%f")[:-3]
        end_str = self.end_time.strftime("%H:%M:%S.%f")[:-3]
        return f"{self.num}\n{start_str} --> {end_str}\n{self.text}"


class Segment:
    def __init__(self, start_time: datetime, end_time: datetime) -> Segment:
        self.start_time = start_time
        self.end_time = end_time


class WebVTT:
    def __init__(self, captions: list[Caption]) -> WebVTT:
        self.captions = captions

    @staticmethod
    def read(filename: str) -> WebVTT:
        with open(filename, "r") as f:
            file_contents = f.read().strip()
            chunks = file_contents.split("\n\n")
            # Check that the first line is "WEBVTT", but exclude it afterwards
            _assert(chunks[0] == "WEBVTT", f"Expected the file to begin with 'WEBVTT', but received '{chunks[0]}'.")
            chunks = chunks[1:]
            captions = [Caption.parse(c) for c in chunks]
        return WebVTT(captions)
    
    def remove(self, segment: Segment) -> WebVTT:
        new_captions = []
        for c in self.captions:
            if not (segment.start_time <= c.start_time <= segment.end_time):
                new_captions.append(c)
        self.captions = new_captions
    
    def apply_to_text(self, f: Callable[[str], str]) -> None:
        for c in self.captions:
            c.text = f(c.text)
    
    def save(self, filename: str) -> WebVTT:
        with open(filename, "w") as f:
            f.write("WEBVTT")
            for c in self.captions:
                f.write(f"\n\n{str(c)}")


if __name__ == "__main__":
    vtt = WebVTT.read(r"..\..\test\ifdfesuosrz3ld1hsdnj_captions.vtt")

    start_time = datetime.strptime("00:07:58.640", "%H:%M:%S.%f")
    end_time = datetime.strptime("00:08:25.920", "%H:%M:%S.%f")
    segment = Segment(start_time, end_time)
    vtt.remove(segment)

    vtt.apply_to_text(lambda x: x.replace("morning", "Morning"))

    vtt.save(r"..\..\test\out.vtt")
